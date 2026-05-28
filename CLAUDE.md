# AI Operations Command Center — Engineering Standards

## Project Overview
AI Operations Command Center — autonomous revenue-pod system with agents, task runners, and a social media pipeline (TikTok/Instagram/YouTube).

**Active revenue pods (focus here):**
- `local_outreach_pod` → **Easy Simple Sites** (easysimplesites.org) — Pitch agent finds MA businesses without websites and pitches $199/$499/$799 static sites
- `market_research_pod` → **Tony Stocks** — daily trading briefs from the trading-bot bridge

**Dormant (do not spawn tasks for):** Spark, Muse, Maker, Market, Frame, Echo. ThePromptVaultUS (Etsy prompt packs) was scrapped 2026-05-23.

## Plan-First Workflow (ENFORCED)
Before writing or modifying ANY code, you MUST:
1. State the problem and what files will change
2. Outline the approach in 3–5 bullet points
3. Identify risks or side effects
4. Wait for explicit approval before proceeding

This applies to all code changes. Simple one-liners are exempt.

## Code Standards
- Python 3.x — follow existing patterns in `runner/` and `agents/`
- No unnecessary abstractions — solve the specific problem, not hypothetical future ones
- No comments unless the WHY is non-obvious
- Trust framework guarantees — only validate at system boundaries

## Safety Rules
- Never `rm -rf`, `git reset --hard`, `DROP TABLE`, or force-push without explicit user confirmation
- The `.claude/hooks/safety-check.ps1` hook enforces this automatically
- All destructive operations require the user to re-state intent explicitly

## PR Review Process
- Use `/review` or `/code-review` for any non-trivial PR before merging
- `code-review@claude-plugins-official` is installed globally

## Multi-Agent Verification
For complex logic changes, use the `dispatching-parallel-agents` skill to spawn two independent Claude agents:
- Agent A: implements the change
- Agent B: independently reviews Agent A's output for logic errors and regressions
Invoke with `/dispatching-parallel-agents` before tackling any task with shared-state risk.

## Token Budget
Claude Code shows context window usage natively (bottom of screen as a %).
- Keep CLAUDE.md and memory files concise — they load every session
- Use `/compact` when context fills during long sessions

## Key Directories
- `runner/` — task runner, tool execution, agent routing
- `agents/` — agent definition markdown files
- `workspace/tasks/` — todo/done task files
- `workspace/outputs/` — agent output files
- `config/` — YAML config files (models, budgets, guardrails, revenue pods)
- `scripts/` — PowerShell automation scripts
- `.claude/hooks/` — Claude Code lifecycle hooks
