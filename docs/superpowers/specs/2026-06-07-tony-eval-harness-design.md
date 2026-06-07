# Design — Tony Walk-Forward Eval Harness + Phase-0 Safety Engine (Project Lighthouse)

**Date:** 2026-06-07 · **Status:** approved-by-operator-handoff (autonomous build authorized; §10 kickoff).
**Source of truth:** `docs/handoffs/2026-06-07-tony-enhancement-buildout-handoff.md`,
`docs/research/2026-06-07-tony-master-roadmap.md`. This file is the implementation design; the
handoff's §4 Iteration Compact is the approved scope.

## Problem
Tony is a paper-trading research agent with a self-learning loop that writes `learned_rules`
back into its own future verdicts. There is **no way to prove a change improves out-of-sample
outcomes before it ships** — the single most dangerous gap before real money (a false "rosy" rule
already biased real verdicts once). We build the **walk-forward eval harness** (keystone) plus the
Phase-0 safety net so autonomous learning becomes trustworthy.

## Non-negotiable invariants (from handoff §7)
1. **Learn from the REAL realized track** (`tony_realized`, Alpaca-reconciled P/L) — never the rosy
   verdict track (`tony_scorecard`, verdict-vs-bot-outcome join). Mirror the existing `_realized_block`
   small-sample discipline. The verdict track is analysis-only in the harness, always flagged rosy.
2. **No leakage** — time-based walk-forward by `resolved_date` (delayed labels); never a random split.
3. **Fail-closed** promotion gates — a missing/insufficient metric blocks promotion, never allows it.
4. **Honesty in numbers** — thin samples reported with CIs and an explicit `insufficient_sample` flag;
   never round a 4-trade sample into a verdict.
5. PAPER only. No live keys, no funding. New trading behavior ships behind OFF flags.

## Data contract (entity grain = one verdict per (symbol, pick_date))
- **Verdicts** (`tony_stocks_verdicts.json`, 103 rows): `date, symbol, verdict, confidence,
  evidence[], tony_score, target, stop, thesis`.
- **Outcomes** (`tony_stocks_outcomes.json`, 50 rows, DELAYED labels): `symbol, pick_date,
  resolved_date, result, entry, exit, return_pct, days_held`.
- **Realized** (`workspace/tony-realized.json`, GROUND TRUTH $): `symbol, qty, entry, exit,
  realized_pl, pct, reason, date, exit_order_id`.
- **Join:** reuse `tony_scorecard._matched_verdict` + `_is_right` verbatim so the harness reproduces
  the LIVE grading rule (baseline-reproduction requirement). Snapshot = sha256 of the three inputs,
  versioned per run.
- **Delayed-label health:** only picks with a `resolved_date` are graded; report resolved vs pending.

## Modules (`runner/eval/`)
- `data_contract.py` — load + join + snapshot hash + health report; leakage-safe ordering by
  `resolved_date`. Pure over injected data; thin fail-soft loaders.
- `metrics.py` — deterministic code graders: win-rate, **return-based expectancy** (mean realized
  `pct`, total `realized_pl` — realized track), **R-multiple expectancy** where stop is known,
  per-confidence **calibration** + monotonicity (high>med>low), **edge mining with Wilson CIs +
  Bayesian (Beta) shrinkage** (kills the `min_n=5` over-trust — T1.6).
- `walk_forward.py` — order graded picks by `resolved_date`; expanding-window train/test folds;
  out-of-sample metrics per fold + aggregate. Replays RECORDED data only (no LLM re-runs).
- `promotion_gate.py` — fail-closed `assert_promotion_ready(report) -> {promote, reasons}`:
  OOS expectancy>0 **on the realized track**, calibration monotonic, max drawdown within threshold,
  edges shrunk, sample ≥ min. Any missing metric ⇒ block.
- `harness.py` — orchestrator: `baseline()` (reproduce live calibration/edges as the regression
  baseline) + `evaluate_candidate(change)` (the "would-this-change-help?" capability: re-grade with a
  candidate rule/sizing applied, walk-forward, compare OOS vs baseline, gate). Writes the Iteration
  Compact artifact.
- CLI/gate: `evals/tony/walk_forward_eval.py` — headless run for the master-always-deployable gate;
  `run()` returns `{ok, ...}`; a pytest asserts it reproduces the live baseline and stays green.

## Phase-0 safety adds (independent leaf modules, code-enforced, LLM-independent)
- `runner/ledger/drawdown_breaker.py` (T1.3) — N consecutive losses OR X% drawdown ⇒ halt/throttle.
- `runner/tools/external_data_guard.py` — sanitize/bound news/web/EDGAR text before it reaches a
  verdict (prompt-injection + fake-level defang).
- `runner/ledger/decision_audit.py` — append-only JSONL audit of every verdict/order/skip/breaker.
- `runner/ledger/cluster_risk.py` (T1.9) — cap simultaneous correlated exposure (energy-cluster).
- Wiring into `alpaca_paper.sync()` is **gated behind OFF flags** (`TONY_BREAKER_ENABLED`,
  `TONY_CLUSTER_CAP_ENABLED`) so live behavior is unchanged until the operator flips them.

## Phase 1 (behind OFF flags, harness-evidenced)
Shrinkage edges (T1.6, in `metrics.py`), $-weighted learning from realized R (T1.5), experience-memory
rule lifecycle + shadow-gate quarantine/promote (T1.2/T1.7), regime-conditioned edges (T1.8).
Conviction sizing (T1.4) already gated via `TONY_CONVICTION_SIZING=auto`; harness supplies the proof.

## Phase 2 (real-money-READY, runs PAPER)
`account_mode.py` — single source of truth for paper↔live (`TONY_ACCOUNT_MODE`, default `paper`);
every guard behaves identically. Cutover runbook + paper-language scrub behind a default-OFF flag.
**No live keys, no funding.**

## Phase 3 (specs only)
Multi-agent council, RL memory, options expansion — design docs, no behavior.

## Testing
TDD throughout; hermetic (inject data / tmp_path); preserve every real bug as a regression slice
(false-rosy-rule, energy-cluster, Friday 4-stop). Gate = full suite + harness green on paper.
