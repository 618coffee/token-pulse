"""Claude Code JSONL session log backend.

Reads ~/.claude/projects/<slug>/<session-uuid>.jsonl files. Each file is one
session; each line is a JSON object representing a user message, assistant
message, or tool result. Assistant messages carry the API `usage` field with
exact input/output/cache token counts.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from ..event import TokenEvent


def default_projects_dir() -> Path:
    override = os.environ.get("CLAUDE_PROJECTS_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "projects"


def _parse_timestamp(s: str) -> datetime:
    # Claude Code timestamps are ISO-8601 with trailing 'Z'.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _extract_files_touched(message: dict) -> List[str]:
    """Return file paths referenced by tool_use blocks in this assistant message."""
    files: List[str] = []
    content = message.get("content")
    if not isinstance(content, list):
        return files
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use":
            continue
        name = block.get("name", "")
        inp = block.get("input") or {}
        # Common Claude Code tools that touch files.
        for key in ("file_path", "filePath", "path", "notebook_path"):
            v = inp.get(key)
            if isinstance(v, str):
                files.append(v)
                break
        # MultiEdit / batched edits.
        if name in {"MultiEdit", "multi_replace_string_in_file"}:
            edits = inp.get("edits") or inp.get("replacements") or []
            if isinstance(edits, list):
                for e in edits:
                    if isinstance(e, dict):
                        for k in ("file_path", "filePath", "path"):
                            v = e.get(k)
                            if isinstance(v, str):
                                files.append(v)
                                break
    # Dedupe preserving order.
    seen = set()
    out = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


class ClaudeCodeBackend:
    name = "claude-code"

    def __init__(self, projects_dir: Optional[Path] = None, cwd_filter: Optional[str] = None):
        self.projects_dir = Path(projects_dir) if projects_dir else default_projects_dir()
        self.cwd_filter = cwd_filter  # if set, only emit events whose cwd starts with this path

    def _iter_jsonl_files(self) -> Iterator[Path]:
        if not self.projects_dir.exists():
            return
        yield from sorted(self.projects_dir.rglob("*.jsonl"))

    def events(self) -> Iterable[TokenEvent]:
        for path in self._iter_jsonl_files():
            yield from self._events_from_file(path)

    def _events_from_file(self, path: Path) -> Iterator[TokenEvent]:
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line_no, raw in enumerate(fh, 1):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        entry = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    ev = self._maybe_event(entry)
                    if ev is None:
                        continue
                    if self.cwd_filter and not (ev.cwd or "").startswith(self.cwd_filter):
                        continue
                    yield ev
        except OSError:
            return

    def _maybe_event(self, entry: dict) -> Optional[TokenEvent]:
        # Only assistant messages carry usage.
        if entry.get("type") != "assistant":
            return None
        msg = entry.get("message") or {}
        usage = msg.get("usage") or {}
        if not usage:
            return None

        ts_raw = entry.get("timestamp")
        if not ts_raw:
            return None
        try:
            ts = _parse_timestamp(ts_raw)
        except ValueError:
            return None

        return TokenEvent(
            timestamp=ts,
            session_id=entry.get("sessionId") or entry.get("session_id") or "",
            backend=self.name,
            model=msg.get("model"),
            cwd=entry.get("cwd"),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
            cache_creation_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
            files_touched=_extract_files_touched(msg),
            estimated=False,
        )
