# Handoff — Staging spends $0 on LLM/APIs (offline by construction)

**For the dual-repo session** (`ai-operations-command-center` + the trading-bot repo).

**The hard requirement, from the operator:** the staging twins are a **functional
tester/debugger ONLY**. They must make **ZERO real LLM/API calls** by default — not "a small
cap," literally $0. Prod LLM spend is ~$50/day and must NOT be doubled by a rehearsal with no
audience. Staging proves the *code works* (no crashes, scheduler fires, sync/ratchet/reconcile/
bridge/reports/dashboard all run) before anything promotes to the 24/7 master branch.

Plan-first applies (state problem/approach/risks, get approval before code). Dev branches only.
CC dev branch: `claude/gracious-euler-dAdgn`.

---

## 1. Why this is easy: one chokepoint (verified)

Every LLM call in CC funnels through a single method:
- `runner/agents/base.py:183` — `self._completion_with_backoff(**kwargs)` is the ONLY network
  call to a model; spend is booked immediately after at `base.py:300` `record_spend(...)`.
- The client is built in `AgentBase.__init__` (`base.py:87-111`) from `VERTEX_PROJECT` /
  `GOOGLE_AI_API_KEY` / `OPENROUTER_API_KEY`.

So one short-circuit at that chokepoint = the entire system runs with **no model call and $0
spend**, while everything downstream of a verdict still executes for real.

## 2. What runs for real at $0 (the point of staging)

The deterministic core — where the dangerous bugs actually live — touches only the **free Alpaca
paper API** and local files, never an LLM: scheduler/`daily_jobs`, `market_clock`/`trading_day`,
`alpaca_paper` sync / `plan_stop_ratchets` / `plan_max_hold_closes` / reconcile / flush,
`position_meta`, `tony_bridge` parsing, realized/scorecard, dashboard, telegram formatters,
reports. Staging exercises ALL of this for $0. The LLM is only the "what does Tony think" step.

## 3. Task A (CC repo) — offline LLM mode + blank keys (two independent $0 guarantees)

**A1 — Offline mode (primary).** In `runner/agents/base.py`, gate the call:
- If `CC_LLM_OFFLINE` is truthy (pick the name; reuse `--no-live-llm` semantics already in the
  scanner's e2e harness if shared), `_completion_with_backoff` returns a **deterministic canned
  completion** instead of calling the client — a real-shaped object: `choices[0].message` with
  content (and, where the role expects tool calls, a canned tool call), `usage` = 0/0 tokens.
- `record_spend` then books **$0** (zero tokens → `calculate_cost` = 0).
- Canned content must be **realistic enough to drive the pipeline**: e.g. the
  `market_research_worker` returns a verdict carrying `symbol/verdict/target/stop/thesis` so
  `plan_orders` → paper trade → reconcile → EOD ledger all run. Seed from a captured real
  response fixture so the shape never drifts. Keep per-role canned outputs minimal but valid.
- Build the client lazily / skip it entirely when offline, so missing keys (A2) don't even error.

**A2 — Blank LLM keys in staging `.env` (backstop).** In `scripts/setup_staging.sh`, add to the
override sweep + staging block so all of these are emptied:
`OPENROUTER_API_KEY=`, `GOOGLE_AI_API_KEY=`, `VERTEX_PROJECT=`, `GOOGLE_CLOUD_PROJECT=`,
`ANTHROPIC_API_KEY=` (+ any other model keys present). Plus `CC_LLM_OFFLINE=1`. Result: even if
the flag is ever missed, there is no credential to bill against — calls fail-soft, still $0.

**A3 — Tests:** offline mode returns canned completion + books $0; the full plan→trade→report
pipeline runs end-to-end under offline mode (assert verdicts produced, paper orders planned,
report rendered, `daily-spend.json` total == 0.0); prod path unchanged when the flag is unset.

## 4. Task B (bot repo) — same on the scanner twin

Enumerate the scanner's real-money surfaces with file:line provenance — LLM calls AND **paid /
rate-limited data vendors** (Finnhub, etc.; a scanner may have $0 LLM but real data-quota cost).
For each: an offline/stub path (it already has `--no-live-llm` in `full_e2e_sync_test.py` — promote
to a runtime service mode) + blank the relevant keys in its staging `.env`. If a vendor is needed
even in staging, use a free/cached/fixture feed, never the paid live one. Document each decision.

## 5. Task C — the rare opt-in (document in both DEVELOPMENT.mds)

- **DEFAULT = OFFLINE, $0.** This is how staging always runs.
- **FULL-FIDELITY (rare, explicit):** ONLY when the change under test *is* the LLM/reasoning path.
  Operator unsets `CC_LLM_OFFLINE` and pastes real keys for that one soak, accepting a few
  cents/dollars, then reverts to offline. Never the default; call it out as the exception.
- State plainly: offline staging does NOT validate Tony's *reasoning quality* — that's not a code
  regression and isn't staging's job. 99% of changes (plumbing) are validated at $0.

## 6. Acceptance

- [ ] Prod path byte-identical when `CC_LLM_OFFLINE` unset (default behavior preserved).
- [ ] Fresh staging `.env`: `CC_LLM_OFFLINE=1` AND all model keys blank.
- [ ] Overnight staging soak → staging's `workspace/ledger/daily-spend.json` total == **$0.00**
      (exact zero, not "under a cap"), AND the pipeline still produced verdicts → paper trades →
      EOD report (functional coverage proven with no spend).
- [ ] Scanner real-money surfaces enumerated + neutralized; both DEVELOPMENT.mds carry the
      offline-default / full-fidelity-opt-in / on-demand (start-for-soak, stop-after-promote) rules.
- [ ] Tests green both repos; pre-existing failures quarantined per deploy rules.

**Note:** a prior draft (`STAGING_COST_CONTROL_HANDOFF.md`) proposed *budget caps* — superseded
by this. Caps still spend; the requirement is zero. Offline-by-construction is both correct and
simpler. All trading everywhere is Alpaca PAPER (fake $); LLM/data tokens are the only real money,
and this handoff fences them to $0 in staging.
