# Contributing to token-pulse

Thanks for your interest! token-pulse is small and tries to stay that way.

## Development setup

```bash
git clone https://github.com/618coffee/token-pulse
cd token-pulse
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,estimate]'
pytest
ruff check src tests
```

## Adding a new scope

1. Add a `cmd_<scope>` handler in `src/token_pulse/cli.py`.
2. Wire it up in `build_parser()`.
3. Reuse `_load_events`, `_filter_window`, and `aggregate` — don't duplicate logic.
4. Add a test in `tests/`.
5. Document the scope in `README.md` and `SKILL.md`.

## Adding a new backend

1. Subclass the `Backend` protocol in `src/token_pulse/backends/`.
2. Yield `TokenEvent` instances. Set `estimated=True` if counts are not exact.
3. Register it in `backends/__init__.py::get_backend`.
4. Add a `--backend <name>` test.
5. Document accuracy caveats in `README.md`.

## Pricing updates

Edit `src/token_pulse/pricing.py::DEFAULT_PRICES`. Reference the provider's pricing page in the commit message.

## Release

1. Bump version in `pyproject.toml` and `src/token_pulse/__init__.py`.
2. Update `CHANGELOG.md`.
3. Tag and push: `git tag v0.x.y && git push --tags`.
4. Create a GitHub release — `publish.yml` auto-publishes to PyPI.

## Code style

- Python ≥ 3.9, type hints encouraged but not enforced.
- Format with `ruff format`; lint with `ruff check`.
- Keep stdlib-only for the core; optional features (e.g. tiktoken) go behind extras.
