# Changelog

All notable changes to token-pulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-23

### Added
- Claude Code JSONL backend (accurate per-turn token counts).
- VS Code GitHub Copilot backend (estimated; uses `tiktoken` if available).
- Scopes: `turn`, `session`, `commit`, `branch`, `pr`, `window`, `file`.
- Per-file attribution via tool-call targets (weighted across files in a turn).
- Pricing table for Anthropic Claude family with prefix-match fallback.
- Text and JSON output formatters; ranking mode for multi-item scopes.
- `SKILL.md` for use as a Claude Code / VS Code Copilot agent skill.
- GitHub Actions CI (Linux + macOS, Python 3.9 / 3.11 / 3.12).
- Trusted-publishing PyPI release workflow.
