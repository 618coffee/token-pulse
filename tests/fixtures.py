"""Synthetic Claude Code JSONL fixture for tests."""

import json
from pathlib import Path

FIXTURE_LINES = [
    # User turn (no usage; should be ignored)
    {
        "type": "user",
        "sessionId": "sess-1",
        "timestamp": "2026-04-22T10:00:00Z",
        "cwd": "/home/dev/repo",
        "message": {"content": "hello"},
    },
    # Assistant turn 1 — touches one file
    {
        "type": "assistant",
        "sessionId": "sess-1",
        "timestamp": "2026-04-22T10:00:05Z",
        "cwd": "/home/dev/repo",
        "message": {
            "model": "claude-sonnet-4-5-20260101",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 1000,
                "cache_creation_input_tokens": 200,
            },
            "content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "src/foo.py"}},
            ],
        },
    },
    # Assistant turn 2 — touches two files (weighted attribution test)
    {
        "type": "assistant",
        "sessionId": "sess-1",
        "timestamp": "2026-04-22T10:05:00Z",
        "cwd": "/home/dev/repo",
        "message": {
            "model": "claude-sonnet-4-5-20260101",
            "usage": {
                "input_tokens": 200,
                "output_tokens": 100,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": "src/foo.py"}},
                {"type": "tool_use", "name": "Write", "input": {"file_path": "src/bar.py"}},
            ],
        },
    },
    # Different session, different cwd (cwd_filter test)
    {
        "type": "assistant",
        "sessionId": "sess-2",
        "timestamp": "2026-04-22T11:00:00Z",
        "cwd": "/home/dev/other",
        "message": {
            "model": "claude-haiku-4",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [{"type": "text", "text": "hi"}],
        },
    },
]


def write_fixture(dest_dir: Path) -> Path:
    """Write fixture into <dest_dir>/<slug>/<sess>.jsonl mimicking ~/.claude/projects layout."""
    project_dir = dest_dir / "-home-dev-repo"
    project_dir.mkdir(parents=True, exist_ok=True)
    f = project_dir / "sess-1.jsonl"
    with f.open("w", encoding="utf-8") as fh:
        for line in FIXTURE_LINES[:3]:
            fh.write(json.dumps(line) + "\n")
    other = dest_dir / "-home-dev-other"
    other.mkdir(parents=True, exist_ok=True)
    f2 = other / "sess-2.jsonl"
    with f2.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(FIXTURE_LINES[3]) + "\n")
    return dest_dir
