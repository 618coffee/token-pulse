"""Backend protocol — each data source yields TokenEvents."""

from __future__ import annotations

from typing import Iterable, Protocol

from ..event import TokenEvent


class Backend(Protocol):
    name: str

    def events(self) -> Iterable[TokenEvent]:
        """Yield all token events available from this backend."""
        ...
