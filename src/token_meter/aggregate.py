"""Aggregate TokenEvents into a Report."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

from .event import TokenEvent
from .pricing import compute_cost


@dataclass
class Report:
    label: str
    backend: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    turn_count: int = 0
    session_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    estimated: bool = False
    models: List[str] = field(default_factory=list)
    cost_estimate: Optional[float] = None
    extra: dict = field(default_factory=dict)

    @property
    def total_input_billable(self) -> int:
        return self.input_tokens + self.cache_creation_tokens

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


def aggregate(events: Iterable[TokenEvent], label: str) -> Report:
    events = list(events)
    if not events:
        return Report(label=label, backend="-")

    sessions: set = set()
    models_counter: Counter = Counter()
    in_t = out_t = cr_t = cc_t = 0
    estimated = False
    backends: set = set()
    earliest = latest = None

    for ev in events:
        sessions.add(ev.session_id)
        if ev.model:
            models_counter[ev.model] += 1
        in_t += ev.input_tokens
        out_t += ev.output_tokens
        cr_t += ev.cache_read_tokens
        cc_t += ev.cache_creation_tokens
        estimated = estimated or ev.estimated
        backends.add(ev.backend)
        if earliest is None or ev.timestamp < earliest:
            earliest = ev.timestamp
        if latest is None or ev.timestamp > latest:
            latest = ev.timestamp

    # Cost: compute per-event so multi-model windows are accurate.
    total_cost = 0.0
    cost_known = False
    for ev in events:
        c = compute_cost(
            ev.model,
            ev.input_tokens,
            ev.output_tokens,
            ev.cache_read_tokens,
            ev.cache_creation_tokens,
        )
        if c is not None:
            total_cost += c
            cost_known = True

    return Report(
        label=label,
        backend=",".join(sorted(backends)) if backends else "-",
        window_start=earliest,
        window_end=latest,
        turn_count=len(events),
        session_count=len(sessions),
        input_tokens=in_t,
        output_tokens=out_t,
        cache_read_tokens=cr_t,
        cache_creation_tokens=cc_t,
        estimated=estimated,
        models=[m for m, _ in models_counter.most_common()],
        cost_estimate=total_cost if cost_known else None,
    )
