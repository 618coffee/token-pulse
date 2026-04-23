"""VS Code GitHub Copilot chat log backend (ESTIMATED).

Reads chat logs from VS Code workspace storage. Token counts are *estimated*
by re-tokenizing message text — they do NOT include hidden system prompts,
tool-call payloads, or cache effects. Use for relative comparison only.

Storage locations (auto-detected per platform):
- macOS:   ~/Library/Application Support/Code/User/workspaceStorage/<id>/GitHub.copilot-chat/
- Linux:   ~/.config/Code/User/workspaceStorage/<id>/GitHub.copilot-chat/
- Windows: %APPDATA%/Code/User/workspaceStorage/<id>/GitHub.copilot-chat/
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Optional

from ..event import TokenEvent


def _vscode_user_dir() -> Optional[Path]:
    override = os.environ.get("VSCODE_USER_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User"
    if sys.platform.startswith("linux"):
        return Path.home() / ".config" / "Code" / "User"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Code" / "User"
    return None


def _estimate_tokens(text: str) -> int:
    """Estimate token count. Uses tiktoken if available, else chars/4 heuristic."""
    if not text:
        return 0
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


class CopilotBackend:
    name = "copilot"

    def __init__(self, user_dir: Optional[Path] = None, cwd_filter: Optional[str] = None):
        self.user_dir = Path(user_dir) if user_dir else _vscode_user_dir()
        self.cwd_filter = cwd_filter

    def _iter_chat_files(self) -> Iterator[Path]:
        if not self.user_dir or not self.user_dir.exists():
            return
        ws_storage = self.user_dir / "workspaceStorage"
        if not ws_storage.exists():
            return
        # Copilot chat stores per-session JSON files under various subpaths;
        # we recursively find any *.json under GitHub.copilot-chat/sessions/.
        for entry in ws_storage.iterdir():
            chat_dir = entry / "GitHub.copilot-chat"
            if not chat_dir.exists():
                continue
            for path in chat_dir.rglob("*.json"):
                yield path

    def events(self) -> Iterable[TokenEvent]:
        for path in self._iter_chat_files():
            yield from self._events_from_file(path)

    def _events_from_file(self, path: Path) -> Iterator[TokenEvent]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        # Heuristic: walk arbitrary structure, find dicts that look like chat
        # turns (have a 'role' or 'type' and some text-bearing field).
        cwd_hint = self._infer_cwd(path)
        session_id = path.stem

        for turn in _walk_turns(data):
            ts = _coerce_ts(turn.get("timestamp") or turn.get("createdAt"))
            if ts is None:
                continue
            user_text = _collect_text(turn.get("request") or turn.get("user") or "")
            asst_text = _collect_text(turn.get("response") or turn.get("assistant") or turn.get("result") or "")
            if not user_text and not asst_text:
                continue
            ev = TokenEvent(
                timestamp=ts,
                session_id=session_id,
                backend=self.name,
                model=turn.get("model"),
                cwd=cwd_hint,
                input_tokens=_estimate_tokens(user_text),
                output_tokens=_estimate_tokens(asst_text),
                cache_read_tokens=0,
                cache_creation_tokens=0,
                files_touched=[],
                estimated=True,
            )
            if self.cwd_filter and not (ev.cwd or "").startswith(self.cwd_filter):
                continue
            yield ev

    def _infer_cwd(self, path: Path) -> Optional[str]:
        # workspaceStorage/<hash>/workspace.json contains the folder URI.
        try:
            ws_root = path.parents[1]
            ws_meta = ws_root / "workspace.json"
            if ws_meta.exists():
                meta = json.loads(ws_meta.read_text(encoding="utf-8"))
                folder = meta.get("folder") or ""
                if folder.startswith("file://"):
                    return folder[len("file://") :]
                return folder or None
        except Exception:
            pass
        return None


def _walk_turns(node) -> Iterator[dict]:
    if isinstance(node, dict):
        # Heuristic: looks like a chat turn?
        if any(k in node for k in ("request", "response", "result")) and (
            "timestamp" in node or "createdAt" in node
        ):
            yield node
        for v in node.values():
            yield from _walk_turns(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_turns(item)


def _collect_text(node) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        for k in ("message", "text", "content", "value"):
            if k in node:
                return _collect_text(node[k])
        # Fall back: concatenate all string values.
        return " ".join(_collect_text(v) for v in node.values())
    if isinstance(node, list):
        return " ".join(_collect_text(x) for x in node)
    return ""


def _coerce_ts(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # ms since epoch heuristic
        seconds = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except ValueError:
            return None
    return None
