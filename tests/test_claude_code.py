from pathlib import Path

import pytest

from token_meter.aggregate import aggregate
from token_meter.backends.claude_code import ClaudeCodeBackend

from .fixtures import write_fixture


@pytest.fixture
def projects_dir(tmp_path: Path) -> Path:
    return write_fixture(tmp_path / "projects")


def test_parses_assistant_events_only(projects_dir):
    events = list(ClaudeCodeBackend(projects_dir=projects_dir).events())
    # 3 assistant events total across both projects.
    assert len(events) == 3
    # First event's exact token counts.
    e0 = next(e for e in events if e.session_id == "sess-1" and e.input_tokens == 100)
    assert e0.input_tokens == 100
    assert e0.output_tokens == 50
    assert e0.cache_read_tokens == 1000
    assert e0.cache_creation_tokens == 200
    assert e0.files_touched == ["src/foo.py"]
    assert not e0.estimated


def test_cwd_filter_restricts_events(projects_dir):
    events = list(
        ClaudeCodeBackend(projects_dir=projects_dir, cwd_filter="/home/dev/repo").events()
    )
    assert len(events) == 2
    assert all(e.cwd == "/home/dev/repo" for e in events)


def test_aggregate_sums_tokens_and_estimates_cost(projects_dir):
    events = list(
        ClaudeCodeBackend(projects_dir=projects_dir, cwd_filter="/home/dev/repo").events()
    )
    report = aggregate(events, label="test")
    assert report.input_tokens == 300
    assert report.output_tokens == 150
    assert report.cache_read_tokens == 1000
    assert report.cache_creation_tokens == 200
    assert report.turn_count == 2
    assert report.session_count == 1
    # Cost should be > 0 since model maps to claude-sonnet-4-5 pricing.
    assert report.cost_estimate is not None
    assert report.cost_estimate > 0


def test_aggregate_handles_empty():
    r = aggregate([], label="empty")
    assert r.turn_count == 0
    assert r.total_tokens == 0
    assert r.cost_estimate is None
