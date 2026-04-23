"""token-meter CLI."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from . import __version__
from .aggregate import Report, aggregate
from .backends import get_backend
from .event import TokenEvent
from .format import render_json, render_ranking, render_text
from .vcs import (
    commit_window,
    fetch_pr,
    head_commit,
    merge_base,
    repo_root,
    resolve_commits,
)


# ---------- helpers ----------


def _parse_iso_loose(s: str) -> datetime:
    """Parse a user-provided datetime — accepts dates, times, full ISO."""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # Accept "HH:MM" as today at that local time.
    if len(s) <= 5 and ":" in s:
        today = datetime.now().astimezone()
        hh, mm = s.split(":")
        return today.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise SystemExit(f"Invalid datetime: {s!r} ({exc})")
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


def _load_events(args, cwd_filter: Optional[str] = None) -> List[TokenEvent]:
    backend = get_backend(args.backend, cwd_filter=cwd_filter)
    return list(backend.events())


def _filter_window(events: Iterable[TokenEvent], start: Optional[datetime], end: Optional[datetime]) -> List[TokenEvent]:
    out = []
    for ev in events:
        if start and ev.timestamp < start:
            continue
        if end and ev.timestamp > end:
            continue
        out.append(ev)
    return out


def _emit(report: Report, json_out: bool) -> None:
    print(render_json(report) if json_out else render_text(report))


def _resolve_cwd_filter(args) -> Optional[str]:
    if getattr(args, "all_repos", False):
        return None
    if getattr(args, "cwd", None):
        return str(Path(args.cwd).expanduser().resolve())
    try:
        return str(repo_root())
    except Exception:
        return None


# ---------- subcommand handlers ----------


def cmd_turn(args) -> int:
    events = _load_events(args, cwd_filter=_resolve_cwd_filter(args))
    if not events:
        print("No token events found.", file=sys.stderr)
        return 1
    events.sort(key=lambda e: e.timestamp)
    last = events[-1]
    report = aggregate([last], label=f"turn @ {last.timestamp.astimezone().isoformat(timespec='seconds')}")
    _emit(report, args.json)
    return 0


def cmd_session(args) -> int:
    events = _load_events(args, cwd_filter=_resolve_cwd_filter(args))
    if not events:
        print("No token events found.", file=sys.stderr)
        return 1
    if args.session_id:
        sid = args.session_id
        events = [e for e in events if e.session_id == sid]
        label = f"session {sid}"
    else:
        events.sort(key=lambda e: e.timestamp)
        sid = events[-1].session_id
        events = [e for e in events if e.session_id == sid]
        label = f"session {sid} (latest)"
    report = aggregate(events, label=label)
    _emit(report, args.json)
    return 0


def cmd_commit(args) -> int:
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else None
    cwd_filter = _resolve_cwd_filter(args)
    commits = resolve_commits(args.spec, cwd=cwd)
    if not commits:
        print(f"No commits matched: {args.spec}", file=sys.stderr)
        return 1
    all_events = _load_events(args, cwd_filter=cwd_filter)

    reports: List[Report] = []
    for commit in commits:
        start, end = commit_window(commit, cwd=cwd)
        events = _filter_window(all_events, start, end)
        label = f"commit {commit.sha[:8]}  \"{commit.subject}\""
        report = aggregate(events, label=label)
        report.window_start = start
        report.window_end = end
        reports.append(report)

    if args.rank or len(reports) > 1:
        reports.sort(key=lambda r: r.total_tokens, reverse=True)
        print(render_ranking(reports, json_out=args.json))
        return 0
    _emit(reports[0], args.json)
    return 0


def cmd_branch(args) -> int:
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else None
    cwd_filter = _resolve_cwd_filter(args)
    base_commit = merge_base(args.base, "HEAD", cwd=cwd)
    head = head_commit(cwd=cwd)
    all_events = _load_events(args, cwd_filter=cwd_filter)
    events = _filter_window(all_events, base_commit.timestamp, head.timestamp if head.timestamp > base_commit.timestamp else None)
    label = f"branch since {args.base} (merge-base {base_commit.sha[:8]})"
    report = aggregate(events, label=label)
    report.window_start = base_commit.timestamp
    report.window_end = head.timestamp
    _emit(report, args.json)
    return 0


def cmd_pr(args) -> int:
    cwd = Path(args.cwd).expanduser().resolve() if args.cwd else None
    cwd_filter = _resolve_cwd_filter(args)
    pr = fetch_pr(args.number, cwd=cwd)
    end = pr.merged_at or pr.closed_at or datetime.now(timezone.utc)
    all_events = _load_events(args, cwd_filter=cwd_filter)
    events = _filter_window(all_events, pr.created_at, end)
    label = f"PR #{pr.number}  \"{pr.title}\""
    report = aggregate(events, label=label)
    report.window_start = pr.created_at
    report.window_end = end
    _emit(report, args.json)
    return 0


def cmd_window(args) -> int:
    start = _parse_iso_loose(args.since) if args.since else None
    end = _parse_iso_loose(args.until) if args.until else None
    cwd_filter = _resolve_cwd_filter(args)
    all_events = _load_events(args, cwd_filter=cwd_filter)
    events = _filter_window(all_events, start, end)
    label_parts = []
    if start:
        label_parts.append(f"since {start.astimezone().isoformat(timespec='minutes')}")
    if end:
        label_parts.append(f"until {end.astimezone().isoformat(timespec='minutes')}")
    label = "window " + " ".join(label_parts) if label_parts else "window (all time)"
    report = aggregate(events, label=label)
    _emit(report, args.json)
    return 0


def cmd_file(args) -> int:
    cwd_filter = _resolve_cwd_filter(args)
    events = _load_events(args, cwd_filter=cwd_filter)

    # Build per-file events with weighted tokens.
    per_file: dict = {}
    for ev in events:
        files = ev.files_touched
        if not files:
            continue
        weight = 1 / len(files)
        for f in files:
            slot = per_file.setdefault(f, [])
            slot.append((ev, weight))

    if args.path:
        target = args.path
        # Allow both absolute and relative matching.
        matched_keys = [
            k for k in per_file
            if k == target or k.endswith("/" + target) or target in k
        ]
        if not matched_keys:
            print(f"No tool-call attribution found for {target!r}.", file=sys.stderr)
            return 1
        events_for_file = []
        for k in matched_keys:
            for ev, weight in per_file[k]:
                # Scale tokens by weight by reconstructing a TokenEvent.
                events_for_file.append(_scale_event(ev, weight))
        report = aggregate(events_for_file, label=f"file {target}")
        _emit(report, args.json)
        return 0

    # --top mode: rank files
    rankings: List[Report] = []
    for f, items in per_file.items():
        scaled = [_scale_event(ev, w) for ev, w in items]
        r = aggregate(scaled, label=f)
        rankings.append(r)
    rankings.sort(key=lambda r: r.total_tokens, reverse=True)
    rankings = rankings[: args.top]
    print(render_ranking(rankings, json_out=args.json))
    return 0


def _scale_event(ev: TokenEvent, weight: float) -> TokenEvent:
    return TokenEvent(
        timestamp=ev.timestamp,
        session_id=ev.session_id,
        backend=ev.backend,
        model=ev.model,
        cwd=ev.cwd,
        input_tokens=int(ev.input_tokens * weight),
        output_tokens=int(ev.output_tokens * weight),
        cache_read_tokens=int(ev.cache_read_tokens * weight),
        cache_creation_tokens=int(ev.cache_creation_tokens * weight),
        files_touched=ev.files_touched,
        estimated=ev.estimated,
    )


# ---------- argparse wiring ----------


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--backend",
        choices=["claude-code", "copilot"],
        default="claude-code",
        help="Data source (default: claude-code).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--cwd",
        help="Restrict events to this working directory (default: current git repo root).",
    )
    parser.add_argument(
        "--all-repos",
        action="store_true",
        help="Don't filter by working directory (include all sessions).",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="token-meter",
        description="Attribute AI assistant token usage to turns, sessions, commits, branches, PRs, time windows, or files.",
    )
    p.add_argument("--version", action="version", version=f"token-meter {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("turn", help="Last assistant turn.")
    _add_common(sp)
    sp.set_defaults(func=cmd_turn)

    sp = sub.add_parser("session", help="A whole session/conversation.")
    sp.add_argument("session_id", nargs="?", help="Session ID (default: latest).")
    _add_common(sp)
    sp.set_defaults(func=cmd_session)

    sp = sub.add_parser("commit", help="A commit or commit range (e.g. HEAD, HEAD~5..HEAD).")
    sp.add_argument("spec", help="Commit spec.")
    sp.add_argument("--rank", action="store_true", help="Rank commits by total tokens.")
    _add_common(sp)
    sp.set_defaults(func=cmd_commit)

    sp = sub.add_parser("branch", help="Everything since branching off --base.")
    sp.add_argument("--base", default="main", help="Base branch (default: main).")
    _add_common(sp)
    sp.set_defaults(func=cmd_branch)

    sp = sub.add_parser("pr", help="A pull request (uses `gh` CLI).")
    sp.add_argument("number", type=int, help="PR number.")
    _add_common(sp)
    sp.set_defaults(func=cmd_pr)

    sp = sub.add_parser("window", help="An arbitrary time window.")
    sp.add_argument("--since", help="ISO datetime, date, or HH:MM.")
    sp.add_argument("--until", help="ISO datetime, date, or HH:MM.")
    _add_common(sp)
    sp.set_defaults(func=cmd_window)

    sp = sub.add_parser("file", help="Per-file attribution from tool-call targets.")
    sp.add_argument("path", nargs="?", help="File path to query (omit with --top to rank).")
    sp.add_argument("--top", type=int, default=10, help="Show top-N files by token cost.")
    _add_common(sp)
    sp.set_defaults(func=cmd_file)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
