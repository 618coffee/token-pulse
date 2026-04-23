from pathlib import Path

import pytest

from token_pulse.backends.claude_code import ClaudeCodeBackend
from token_pulse.cli import _filter_window, _scale_event
from token_pulse.aggregate import aggregate

from .fixtures import write_fixture
from datetime import datetime, timezone


@pytest.fixture
def all_events(tmp_path: Path):
    write_fixture(tmp_path / "p")
    return list(ClaudeCodeBackend(projects_dir=tmp_path / "p").events())


def test_window_filter_inclusive(all_events):
    start = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 22, 10, 10, 0, tzinfo=timezone.utc)
    filtered = _filter_window(all_events, start, end)
    assert len(filtered) == 2  # both repo events, not the other-cwd one


def test_window_filter_unbounded(all_events):
    assert len(_filter_window(all_events, None, None)) == len(all_events)


def test_scale_event_weights_tokens(all_events):
    ev = all_events[0]
    scaled = _scale_event(ev, 0.5)
    assert scaled.input_tokens == ev.input_tokens // 2
    assert scaled.output_tokens == ev.output_tokens // 2


def test_per_file_attribution_via_aggregate(all_events):
    """Turn 2 touches foo.py and bar.py — each should get half the tokens."""
    foo_events = []
    for ev in all_events:
        if "src/foo.py" in ev.files_touched:
            weight = 1 / len(ev.files_touched)
            foo_events.append(_scale_event(ev, weight))
    r = aggregate(foo_events, label="src/foo.py")
    # Turn 1: 100 input * 1.0 = 100; Turn 2: 200 input * 0.5 = 100; total 200.
    assert r.input_tokens == 200
