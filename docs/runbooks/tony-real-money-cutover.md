# Runbook — Tony Real-Money Cutover (Phase 2/3)

**Status:** plumbing built, runs PAPER. **No live keys, no funding** until the operator runs this on
cutover day, after 1–2 weeks of clean paper AND the eval harness proves expectancy.

The execution path is **account-agnostic** (`runner/ledger/account_mode.py`): going live changes
**config + keys + one flag only** — no code is rearchitected, and every guard behaves identically on
paper and live.

## Pre-cutover gate (ALL must hold — do not flip a single flag before this)
1. Eval harness promotion gate returns `promote: true`
   (`python evals/tony/walk_forward_eval.py` → `promotion.promote == true`). Today it correctly
   returns **false** (realized sample n=4, thin).
2. `tony_live_guard` passes on the real record: ≥ 50 graded verdicts AND win-rate ≥ 60%.
3. 1–2 weeks of clean paper on the VM: brackets/OCO/throttle all firing correctly.
4. Compliance gate cleared (separate track; hard gate before the first **paid** dollar — not a
   trading prerequisite, but on the program's critical path before monetization).

## Cutover steps (cutover day, on the VM, operator-run)
1. Open a **separate** Alpaca account (NOT the bot's) and fund the session size ($5k–$25k).
   Account isolation is a hard rule (§5.3) — `account_mode.live_preconditions` REFUSES if the live
   key equals the bot's `ALPACA_API_KEY`.
2. Set the live env (VM only, never committed):
   - `TONY_LIVE_ALPACA_API_KEY`, `TONY_LIVE_ALPACA_SECRET_KEY` (the isolated account)
   - `TONY_LIVE_ENABLED=1` (operator opt-in, gates `tony_live_guard`)
   - `TONY_ACCOUNT_MODE=live`
3. Enable the code-enforced safety guards (recommend enabling these on PAPER first):
   - `TONY_BREAKER_ENABLED=on` — drawdown circuit breaker
   - `TONY_CLUSTER_CAP_ENABLED=on` — correlated-cluster cap
   - `TONY_DECISION_AUDIT=on` — append-only decision audit log
4. Confirm the throttle/halt thresholds (T0.3) are modeled from Tony's real drawdown/vol data
   (`TONY_BREAKER_MAX_DRAWDOWN_PCT`, `TONY_BREAKER_MAX_CONSEC_LOSSES`).
5. First week: smaller size, watch fills/brackets/OCO/throttle. Kill-switch = `touch
   workspace/TONY_LIVE_KILL` (gates `tony_live_guard` immediately).

## Rollback
`TONY_ACCOUNT_MODE=paper` (or `touch workspace/TONY_LIVE_KILL`) → instantly back to paper. Revert to
the prior tagged master + `cc-runner` restart for code rollback.

## Flag inventory (all default OFF/paper — nothing changes until set)
| Flag | Default | Effect |
|---|---|---|
| `TONY_ACCOUNT_MODE` | `paper` | `live` routes to the isolated real account (gated) |
| `TONY_LIVE_ENABLED` | unset | operator opt-in for `tony_live_guard` |
| `TONY_LIVE_ALPACA_API_KEY` / `_SECRET_KEY` | unset | the SEPARATE live account keys |
| `TONY_BREAKER_ENABLED` | off | drawdown circuit breaker halt/throttle |
| `TONY_BREAKER_MAX_CONSEC_LOSSES` | 3 | consecutive-loss halt threshold |
| `TONY_BREAKER_MAX_DRAWDOWN_PCT` | 8.0 | peak-to-trough drawdown halt threshold |
| `TONY_BREAKER_THROTTLE_MULT` | 0.5 | size multiplier in the soft zone |
| `TONY_CLUSTER_CAP_ENABLED` | off | correlated-cluster exposure cap |
| `TONY_MAX_PER_CLUSTER` | 3 | max simultaneous positions per cluster |
| `TONY_DECISION_AUDIT` | off | append-only decision audit JSONL |
| `TONY_CONVICTION_SIZING` | off | conviction sizing (off/on/auto) — auto needs harness-proven calibration |
| `TONY_INPUT_GUARD` | off | external-data injection guard on news/web (wire at the tool boundary) |

## Paper-language scrub (cutover-day one-pass)
Public surfaces should read `account_mode.money_label()` ("paper"/"real") instead of hardcoding
"paper". Inventory the spots (Telegram alerts, daily/weekly synthesis, notify copy) at flip; the
switch is the single `TONY_ACCOUNT_MODE` flag. **Do this only at cutover** — pre-cutover content must
not claim performance/account type (front-running + honesty guards hold).
