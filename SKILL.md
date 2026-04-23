---
name: token-pulse
description: Attribute AI assistant token usage to turns, sessions, git commits, branches, pull requests, time windows, or individual files. Use when the user asks how many tokens a turn/session/commit/PR/branch/file cost, wants to compare token spend between commits, identify expensive turns, audit context consumption, or estimate cost for a development task. Works with Claude Code session JSONL logs (accurate) and VS Code GitHub Copilot chat logs (estimated). Trigger phrases include "token usage", "how many tokens", "cost of this PR", "expensive commit", "context burn", "session cost", "rank token usage".
---

# token-pulse — Token Usage Attribution

## When to use this skill

Invoke `token-pulse` when the user asks any of:

- "How many tokens did this turn / session / commit / branch / PR cost?"
- "Which commit was the most expensive?"
- "Show me my token spend in the last hour."
- "Which file is eating the most context?"
- "How much did I spend on the agent today?"
- "Compare token usage between these two commits."

**Do NOT** invoke for:
- Reducing token usage (that's `caveman` or `compress`).
- Counting tokens in a string (use `tiktoken` directly).
- Live API quota/rate-limit checks (use the provider dashboard).

## How to use

`token-pulse` is a CLI. Run it via the terminal. Subcommands map directly to scopes:

| User intent | Command |
|---|---|
| Last assistant turn | `token-pulse turn` |
| Current session | `token-pulse session` |
| A specific commit | `token-pulse commit <sha>` |
| Range of commits | `token-pulse commit <from>..<to>` |
| Since branching off main | `token-pulse branch --base main` |
| A pull request | `token-pulse pr <number>` |
| Custom time window | `token-pulse window --since <iso> --until <iso>` |
| Per-file attribution | `token-pulse file <path>` or `token-pulse file --top 10` |
| Machine-readable output | append `--json` |

### Recommended workflow

1. **Confirm install**: `token-pulse --version`. If missing, suggest `pipx install token-pulse`.
2. **Pick the right scope**:
   - If the user mentions a SHA, branch name, or PR number → use that scope directly.
   - If they say "this commit" / "the last commit" → `token-pulse commit HEAD`.
   - If they say "today" / "this morning" → `token-pulse window --since <iso>`.
   - If they say "this session" / "this conversation" → `token-pulse session`.
3. **Run the command** and present the output verbatim (it's already formatted).
4. **For ranking questions** ("which commit was most expensive?") add `--rank` to commit-range queries.
5. **For Copilot users** add `--backend copilot` and warn the result is estimated.

### Example invocations

```bash
# "How much did the last 5 commits cost in tokens?"
token-pulse commit HEAD~5..HEAD --rank

# "Which file in this repo eats the most context?"
token-pulse file --top 10

# "Token cost of PR #128?"
token-pulse pr 128
```

## Output interpretation

`token-pulse` reports four token classes:

- **Input tokens** — fresh prompt tokens billed at full rate.
- **Output tokens** — assistant-generated tokens.
- **Cache read** — prompt tokens served from cache (cheap, ~10% of input rate for Anthropic).
- **Cache creation** — tokens written to cache (slightly more expensive than input).

The "Estimated cost" line uses built-in pricing (overridable via `~/.config/token-pulse/config.toml`). Always present cost as **estimated** unless the user is on a metered API key for which the model+pricing is known-current.

## Caveats to surface to the user

- **Copilot backend is estimation only** — re-tokenizes saved chat text and misses system prompts, tool payloads, and cache. Typically under-counts by 30–60%. Use for relative comparison, not billing.
- **Per-file attribution** splits each turn's tokens equally across files touched by tool calls in that turn — a heuristic, not exact.
- **PR scope requires `gh` CLI** authenticated to the target repo.
- **Time windows on commit/branch/PR** are derived from log timestamps; if the user worked on multiple repos in the same window, filter by `--cwd` (defaults to current repo root).

## Troubleshooting

- `No JSONL files found` → check `~/.claude/projects/` exists; user may not have used Claude Code in this repo. Suggest `--cwd` override or `--backend copilot`.
- `gh: command not found` (PR scope) → install GitHub CLI or use `--since`/`--until` instead.
- Numbers seem too low → check `--backend` (default is claude-code; copilot under-counts).
