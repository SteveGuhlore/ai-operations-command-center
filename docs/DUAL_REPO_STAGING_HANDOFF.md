# START HERE — Dual-repo staging session: make both twins $0-by-construction

You are in a session with BOTH repos attached:
- `ai-operations-command-center` (CC) — checkout `/opt/command-center`, dev branch
  **`claude/gracious-euler-dAdgn`**
- the trading-bot / scanner repo — checkout `/opt/trading-bot`, its own dev branch

## Mission (one sentence)
The CC and scanner **staging twins already exist**; finish them so a soak makes **ZERO real
LLM/API spend** — staging is a functional tester/debugger only, never a second producer. Prod
LLM spend is ~$50/day and must not be doubled by a rehearsal with no audience.

## Operating rules (non-negotiable)
- **Plan-first:** for each repo, state problem → approach (3–5 bullets) → risks, and get operator
  approval BEFORE writing code (CC `CLAUDE.md` rule; assume the same on the scanner repo).
- **Dev branches only.** Never commit to `master` / the scanner's deploy branch.
- **Never run anything on the VM** or touch the production services (`cc-runner`,
  `tradingbot-api`, `tradingbot-web`). You are writing + testing code only. The operator runs the
  setup scripts on the VM after market close.
- **Quarantine, don't fix, pre-existing test failures** (failures that reproduce with your changes
  stashed) — report them, don't let them block.

## Current state (what already exists — don't rebuild)
- **CC:** `scripts/setup_staging.sh` (worktree `/opt/command-center-staging`, :8766, isolated
  `.env`, sends hard-off), `scripts/promote_staging.sh` (pytest + readiness + liveness gate),
  `docs/DEVELOPMENT.md`.
- **Scanner:** the prior session shipped `scripts/setup_staging.sh` (worktree
  `/opt/trading-bot-staging`, own venv, `tradingbot-api-staging` :8002 + `tradingbot-watch-staging`
  units), `scripts/promote_staging.sh`, `docs/DEVELOPMENT.md`, and repoints into staging-CC's
  `workspace/trading-reports/`.
- **Gap to close:** neither twin yet guarantees $0 LLM spend. By default each gets its OWN fresh
  spend ledger ($80/day allowance) and the off-hours research lane is UNCAPPED. That is the hole
  this session closes — by going **offline**, not by capping.

## The work (ordered)
1. **CC zero-spend** — implement the offline LLM mode + blank-keys backstop per
   **`docs/STAGING_COST_CONTROL_HANDOFF.md` §3** (chokepoint is `runner/agents/base.py:183`
   `_completion_with_backoff`; spend booked at `:300`). Two independent $0 guarantees:
   `CC_LLM_OFFLINE=1` (canned, real-shaped completions that still drive the pipeline) **and** all
   model keys blanked in the staging `.env` block of `setup_staging.sh`.
2. **Scanner zero-spend** — same retrofit on `/opt/trading-bot` per
   **`docs/STAGING_COST_CONTROL_HANDOFF.md` §4**: enumerate LLM **and paid/rate-limited data**
   surfaces with file:line provenance, neutralize each (offline path — it already has
   `--no-live-llm` in `full_e2e_sync_test.py`; promote it to a runtime service mode — plus blank
   keys / cached-or-free data feeds).
3. **Docs** — both `DEVELOPMENT.md`s carry: offline-default ($0), the rare full-fidelity opt-in,
   and the on-demand rule (start-for-soak, stop-after-promote). Per
   **`docs/STAGING_COST_CONTROL_HANDOFF.md` §5**.
4. **Verify** — acceptance in **`docs/STAGING_COST_CONTROL_HANDOFF.md` §6**: after an offline run,
   staging's `workspace/ledger/daily-spend.json` total is **exactly $0.00**, AND the pipeline still
   produced verdicts → paper trades → EOD report (functional coverage with no spend). Tests green
   both repos.

## Reference docs (read these — all on the CC dev branch)
- `docs/STAGING_COST_CONTROL_HANDOFF.md` — the detailed zero-spend spec (primary).
- `docs/SCANNER_STAGING_HANDOFF.md` — scanner twin recipe + verified VM layout (`/opt/trading-bot`,
  `tradingbot-{api,web}`, shared reports dir `/opt/trading-bot/reports`, the symlink reality).
- `docs/DEVELOPMENT.md` (both repos) — the soak→promote workflow.

## The contract this delivers (confirmed with the operator)
Staging is a **functionally faithful copy of the live VM** — same code (dev-branch candidate vs
prod's `master`; that delta IS the test), same venv/systemd/cron-cycle shape, same real Alpaca
**paper** API, same scheduler/clock/reconcile machinery — **except** it is hermetically sealed:
- LLM **offline, $0** (canned verdicts drive the real pipeline)
- a **separate** paper account (no shared-book corruption)
- Telegram/SendGrid/Instagram **hard-off**
- own port/folder/state; verdict write-back severed from the bot's live reports dir
- **on-demand**, not 24/7

Honest limits to keep in the docs: offline staging validates the **code**, not Tony's reasoning
quality (covered by the rare full-fidelity opt-in); and staging starts with an **empty paper book**
unless a specific test seeds positions. Nothing in this system touches real money — all trading is
Alpaca paper; LLM/data tokens are the only real spend, and this session fences them to $0.

The workflow this locks in (already ENFORCED in CC `CLAUDE.md`):
**dev branch → soak in staging (one evening, $0) → `promote_staging.sh` gate → fast-forward
master → VM restart, outside market hours.**
