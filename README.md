# tokmeter

Attribute AI assistant token usage to **turns, sessions, commits, branches, PRs, time windows, or files** — answering questions like *"how many tokens did this PR cost me?"*

Reads local Claude Code session logs (`~/.claude/projects/**/*.jsonl`) for accurate per-turn API token counts (input / output / cache_read / cache_creation), and provides an estimated mode for VS Code GitHub Copilot chat logs.

> **Status:** v0.1 — Claude Code backend is accurate. Copilot backend is best-effort estimation.

## Install

```bash
# pipx (recommended)
pipx install tokmeter

# or pip
pip install tokmeter

# with optional tiktoken-based estimation for Copilot logs
pip install 'tokmeter[estimate]'
```

## Quick start

```bash
# Last conversation turn
tokmeter turn

# Current session
tokmeter session

# A specific commit
tokmeter commit HEAD
tokmeter commit a1b2c3d

# Range of commits
tokmeter commit HEAD~5..HEAD

# Everything since branching off main
tokmeter branch --base main

# A pull request (uses `gh` CLI)
tokmeter pr 1234

# Arbitrary time window
tokmeter window --since "2026-04-20" --until "2026-04-22"

# Per-file attribution from tool calls (Edit/Write/Read targets)
tokmeter file src/foo.py

# JSON output for piping
tokmeter session --json
```

### Sample output

```
Scope: commit a1b2c3d  "feat: add scoring service"
Window: 2026-04-22 14:31:08 → 2026-04-22 15:08:47 (37m 39s)
Backend: claude-code (12 turns, 1 session)

  Input tokens:           48,210
  Output tokens:          12,883
  Cache read:            312,456
  Cache creation:         18,902
  ─────────────────────────────
  Billable in:            67,112
  Billable out:           12,883

  Estimated cost:         $0.42  (claude-sonnet-4-5)
```

## Why?

Existing tools (`ccusage`, `splitrail`, etc.) give you per-day/per-session totals. `tokmeter` lets you slice the **same underlying data** by VCS-meaningful boundaries:

| Question | Command |
|---|---|
| How much did this PR cost? | `tokmeter pr 42` |
| Which commit was most token-expensive? | `tokmeter commit HEAD~10..HEAD --rank` |
| Which file consumes the most agent context? | `tokmeter file --top 10` |
| What was the burn rate this morning? | `tokmeter window --since 09:00` |

## Backends

### `claude-code` (default, accurate)
Parses JSONL files in `~/.claude/projects/` (override with `CLAUDE_PROJECTS_DIR`). Token counts come straight from the Anthropic API `usage` field — exact, including cache hits.

### `copilot` (estimated, opt-in)
Parses VS Code workspace storage chat logs (`~/Library/Application Support/Code/User/workspaceStorage/<id>/GitHub.copilot-chat/`). Token counts are *estimated* by re-tokenizing message text with `tiktoken` (or a `chars/4` heuristic if `tiktoken` is not installed). **Does not include hidden system prompts or tool-call payloads**, so expect 30–60% under-counting. Useful for relative comparisons, not billing.

```bash
tokmeter session --backend copilot
```

## Use as an agent skill

This repo doubles as an agent skill (Claude Code & VS Code Copilot). Drop the repo into your skills dir:

```bash
# Claude Code
git clone https://github.com/618coffee/tokmeter ~/.claude/skills/tokmeter

# VS Code Copilot (workspace-scoped)
git clone https://github.com/618coffee/tokmeter .github/skills/tokmeter
```

Then ask your agent: *"How many tokens did the last commit cost?"* and it will run `tokmeter commit HEAD` for you. See [SKILL.md](SKILL.md).

## Configuration

Optional `~/.config/tokmeter/config.toml`:

```toml
default_backend = "claude-code"
default_currency = "USD"

[pricing.overrides]
"claude-sonnet-4-5" = { input = 3.00, output = 15.00, cache_read = 0.30, cache_creation = 3.75 }  # $/Mtok
```

## Limitations

- Copilot backend is estimation only (see above).
- PR scope requires the [`gh` CLI](https://cli.github.com/) authenticated to the repo.
- Per-file attribution is heuristic: assistant turn tokens are split equally across files touched by `tool_use` blocks in that turn.
- Time-window filtering uses entry `timestamp`; clock skew between machines may cause edge-case misattribution.

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
