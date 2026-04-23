"""Core data model: a normalized token-usage event."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class TokenEvent:
    """One assistant turn's token usage, normalized across backends."""

    timestamp: datetime
    session_id: str
    backend: str  # "claude-code" | "copilot"
    model: Optional[str] = None
    cwd: Optional[str] = None  # working directory where the turn happened

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    # Files touched by tool_use blocks in this turn (Edit/Write/Read targets).
    files_touched: List[str] = field(default_factory=list)

    # True when token counts are estimated (e.g. Copilot backend).
    estimated: bool = False

    @property
    def total_billable_input(self) -> int:
        return self.input_tokens + self.cache_creation_tokens

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )
