"""Git/PR helpers — call out to `git` and `gh` via subprocess (no extra deps)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple


def _run(cmd: List[str], cwd: Optional[Path] = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}"
        )
    return result.stdout


def repo_root(start: Optional[Path] = None) -> Path:
    out = _run(["git", "rev-parse", "--show-toplevel"], cwd=start or Path.cwd())
    return Path(out.strip())


@dataclass
class Commit:
    sha: str
    timestamp: datetime
    author_email: str
    subject: str


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def resolve_commits(spec: str, cwd: Optional[Path] = None) -> List[Commit]:
    """Resolve a commit spec ('HEAD', 'a1b2c3', 'HEAD~5..HEAD') to a list of commits."""
    fmt = "%H%x09%aI%x09%ae%x09%s"
    if ".." in spec:
        out = _run(["git", "log", spec, f"--pretty=format:{fmt}"], cwd=cwd)
    else:
        out = _run(["git", "log", "-1", spec, f"--pretty=format:{fmt}"], cwd=cwd)
    commits: List[Commit] = []
    for line in out.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        sha, ts, email, subject = parts[0], parts[1], parts[2], "\t".join(parts[3:])
        commits.append(Commit(sha=sha, timestamp=_parse_iso(ts), author_email=email, subject=subject))
    return commits


def commit_window(commit: Commit, cwd: Optional[Path] = None) -> Tuple[datetime, datetime]:
    """Return (start, end) timestamp window attributed to this commit.

    Start = previous commit's time on the same branch (or commit time - 24h if root).
    End = commit's own author timestamp.
    """
    fmt = "%aI"
    try:
        out = _run(
            ["git", "log", "-1", f"{commit.sha}~1", f"--pretty=format:{fmt}"], cwd=cwd
        )
        prev = _parse_iso(out.strip())
    except RuntimeError:
        # Root commit — use a 24h pre-window.
        from datetime import timedelta

        prev = commit.timestamp - timedelta(hours=24)
    return prev, commit.timestamp


def merge_base(base: str, head: str = "HEAD", cwd: Optional[Path] = None) -> Commit:
    sha = _run(["git", "merge-base", base, head], cwd=cwd).strip()
    return resolve_commits(sha, cwd=cwd)[0]


def head_commit(cwd: Optional[Path] = None) -> Commit:
    return resolve_commits("HEAD", cwd=cwd)[0]


# ---------- GitHub PR ----------


@dataclass
class PullRequest:
    number: int
    title: str
    created_at: datetime
    merged_at: Optional[datetime]
    closed_at: Optional[datetime]
    head_ref: str
    base_ref: str


def fetch_pr(number: int, cwd: Optional[Path] = None) -> PullRequest:
    """Use `gh` CLI to fetch PR metadata. Requires gh installed and authenticated."""
    try:
        out = _run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--json",
                "number,title,createdAt,mergedAt,closedAt,headRefName,baseRefName",
            ],
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "`gh` CLI not found. Install from https://cli.github.com/ "
            "or use --since/--until instead."
        ) from exc

    data = json.loads(out)
    return PullRequest(
        number=int(data["number"]),
        title=data.get("title", ""),
        created_at=_parse_iso(data["createdAt"]),
        merged_at=_parse_iso(data["mergedAt"]) if data.get("mergedAt") else None,
        closed_at=_parse_iso(data["closedAt"]) if data.get("closedAt") else None,
        head_ref=data.get("headRefName", ""),
        base_ref=data.get("baseRefName", ""),
    )
