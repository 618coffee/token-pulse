from token_pulse.pricing import compute_cost, lookup_price


def test_lookup_price_exact():
    p = lookup_price("claude-sonnet-4-5")
    assert p is not None
    assert p.input == 3.00


def test_lookup_price_prefix_match():
    p = lookup_price("claude-sonnet-4-5-20260101")
    assert p is not None
    assert p.input == 3.00


def test_lookup_price_unknown_returns_none():
    assert lookup_price("gpt-5-magic") is None
    assert lookup_price(None) is None


def test_compute_cost_math():
    # 1M input tokens of sonnet-4-5 at $3/M = $3.00
    cost = compute_cost("claude-sonnet-4-5", 1_000_000, 0, 0, 0)
    assert cost == 3.00
    # Mixed
    cost = compute_cost("claude-sonnet-4-5", 1000, 1000, 1000, 1000)
    expected = (1000 * 3 + 1000 * 15 + 1000 * 0.30 + 1000 * 3.75) / 1_000_000
    assert abs(cost - expected) < 1e-9


def test_compute_cost_unknown_model_returns_none():
    assert compute_cost("unknown-model", 1000, 1000, 0, 0) is None
