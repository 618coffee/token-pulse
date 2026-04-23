"""Pricing tables ($/Mtok) and cost computation.

Conservative defaults for popular models. Override via config file or CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ModelPrice:
    input: float          # $ per million input tokens
    output: float         # $ per million output tokens
    cache_read: float     # $ per million cache-read tokens
    cache_creation: float # $ per million cache-creation tokens


# Defaults reflect Anthropic public pricing (as of early 2026). Update via
# ~/.config/tokmeter/config.toml [pricing.overrides] if these go stale.
DEFAULT_PRICES: Dict[str, ModelPrice] = {
    "claude-sonnet-4-5":      ModelPrice(3.00, 15.00, 0.30, 3.75),
    "claude-sonnet-4":        ModelPrice(3.00, 15.00, 0.30, 3.75),
    "claude-opus-4":          ModelPrice(15.00, 75.00, 1.50, 18.75),
    "claude-opus-4-7":        ModelPrice(15.00, 75.00, 1.50, 18.75),
    "claude-haiku-4":         ModelPrice(0.80, 4.00, 0.08, 1.00),
    "claude-3-5-sonnet":      ModelPrice(3.00, 15.00, 0.30, 3.75),
    "claude-3-5-haiku":       ModelPrice(0.80, 4.00, 0.08, 1.00),
    "claude-3-opus":          ModelPrice(15.00, 75.00, 1.50, 18.75),
}


def lookup_price(model: Optional[str], overrides: Optional[Dict[str, ModelPrice]] = None) -> Optional[ModelPrice]:
    if not model:
        return None
    if overrides and model in overrides:
        return overrides[model]
    if model in DEFAULT_PRICES:
        return DEFAULT_PRICES[model]
    # Try a longest-prefix match (e.g. "claude-sonnet-4-5-20250619" -> "claude-sonnet-4-5").
    candidates = sorted(DEFAULT_PRICES.keys(), key=len, reverse=True)
    for key in candidates:
        if model.startswith(key):
            return DEFAULT_PRICES[key]
    return None


def compute_cost(
    model: Optional[str],
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
    overrides: Optional[Dict[str, ModelPrice]] = None,
) -> Optional[float]:
    price = lookup_price(model, overrides)
    if price is None:
        return None
    return (
        input_tokens * price.input
        + output_tokens * price.output
        + cache_read_tokens * price.cache_read
        + cache_creation_tokens * price.cache_creation
    ) / 1_000_000
