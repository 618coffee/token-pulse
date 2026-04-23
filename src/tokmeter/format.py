"""Output formatters: human-readable table and JSON."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import List

from .aggregate import Report


def _fmt_int(n: int) -> str:
    return f"{n:>14,}"


def _fmt_dt(dt) -> str:
    if dt is None:
        return "—"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _fmt_duration(start, end) -> str:
    if not start or not end or end < start:
        return "—"
    delta = end - start
    secs = int(delta.total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def render_text(report: Report) -> str:
    lines = []
    lines.append(f"Scope:    {report.label}")
    lines.append(
        f"Window:   {_fmt_dt(report.window_start)} → {_fmt_dt(report.window_end)}"
        f"  ({_fmt_duration(report.window_start, report.window_end)})"
    )
    backend_note = report.backend
    if report.estimated:
        backend_note += "  [ESTIMATED]"
    lines.append(
        f"Backend:  {backend_note}  "
        f"({report.turn_count} turn{'s' if report.turn_count != 1 else ''}, "
        f"{report.session_count} session{'s' if report.session_count != 1 else ''})"
    )
    if report.models:
        lines.append(f"Models:   {', '.join(report.models)}")
    lines.append("")
    lines.append(f"  Input tokens:        {_fmt_int(report.input_tokens)}")
    lines.append(f"  Output tokens:       {_fmt_int(report.output_tokens)}")
    lines.append(f"  Cache read:          {_fmt_int(report.cache_read_tokens)}")
    lines.append(f"  Cache creation:      {_fmt_int(report.cache_creation_tokens)}")
    lines.append("  " + "─" * 36)
    lines.append(f"  Billable input:      {_fmt_int(report.total_input_billable)}")
    lines.append(f"  Billable output:     {_fmt_int(report.output_tokens)}")
    lines.append(f"  Total tokens:        {_fmt_int(report.total_tokens)}")
    if report.cost_estimate is not None:
        marker = "~" if report.estimated else ""
        lines.append("")
        lines.append(f"  Estimated cost:      {marker}${report.cost_estimate:,.4f}")
    if report.estimated:
        lines.append("")
        lines.append("  ⚠ Token counts are estimated (Copilot backend). Use for")
        lines.append("    relative comparison only — not for billing.")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    d = asdict(report)
    for k in ("window_start", "window_end"):
        v = d.get(k)
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return json.dumps(d, indent=2, default=str)


def render_ranking(reports: List[Report], json_out: bool = False) -> str:
    if json_out:
        return json.dumps(
            [
                {
                    "label": r.label,
                    "total_tokens": r.total_tokens,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "cache_read_tokens": r.cache_read_tokens,
                    "cache_creation_tokens": r.cache_creation_tokens,
                    "cost_estimate": r.cost_estimate,
                    "turn_count": r.turn_count,
                }
                for r in reports
            ],
            indent=2,
        )
    if not reports:
        return "(no data)"
    rows = []
    rows.append(f"{'#':>3}  {'TOTAL':>12}  {'IN':>10}  {'OUT':>10}  {'CACHE_R':>11}  {'COST':>10}  LABEL")
    rows.append("-" * 100)
    for i, r in enumerate(reports, 1):
        cost = f"${r.cost_estimate:,.3f}" if r.cost_estimate is not None else "—"
        rows.append(
            f"{i:>3}  {r.total_tokens:>12,}  {r.input_tokens:>10,}  "
            f"{r.output_tokens:>10,}  {r.cache_read_tokens:>11,}  "
            f"{cost:>10}  {r.label}"
        )
    return "\n".join(rows)
