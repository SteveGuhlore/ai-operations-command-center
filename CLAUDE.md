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

## Branch Discipline (ENFORCED — production runs 24/7)
The VM (`/opt/command-center`, systemd `cc-runner`) deploys from `master`. Broken code on
master = broken live service and live paper-trading. **No change ever touches prod directly** —
not a hot edit, not a direct commit, not a restart-with-uncommitted-code.
1. ALL development happens on a dev branch — never commit straight to master
2. Soak the branch in the staging twin (`/opt/command-center-staging`, port 8766,
   service `cc-runner-staging`) for at least one evening of live market data
3. Promote only via `scripts/promote_staging.sh` (full test suite + readiness check must pass),
   and only OUTSIDE market hours (after 4 PM ET) — master advances ff-only to the soaked commit
4. Production deploy = fast-forward pull on the VM + `cc-runner` restart + readiness sweep

## Staging Twin Rules (ENFORCED — see docs/STAGING_WORKFLOW.md for the full runbook)
Staging is a tester/debugger ONLY — never a second producer:
- **$0 spend:** staging runs `CC_LLM_OFFLINE=1` with ALL model keys blank (canned verdicts drive
  the real pipeline). Its `daily-spend.json` must read exactly 0.0. Never put real LLM keys in
  staging except the documented full-fidelity opt-in, reverted after one soak.
- **Own paper account:** staging trades its OWN throwaway Alpaca paper account — never prod's
  keys. Verify before every start: `grep -nE '^ALPACA_(API_KEY|SECRET_KEY)=' <staging>/.env`.
- **On-demand:** start for a soak, stop after promotion (`systemctl start/stop`, never `enable`
  — staging units must not survive a reboot).
- **Claude sessions never run VM commands against the prod checkout.** Staging shell commands are
  given to the operator to run; prod deploys happen only via the promote-gate output.
- The scanner repo (`/opt/trading-bot`, twin `/opt/trading-bot-staging`, flag `TONY_LLM_OFFLINE`)
  follows the identical rules — its own CLAUDE.md carries them.

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
