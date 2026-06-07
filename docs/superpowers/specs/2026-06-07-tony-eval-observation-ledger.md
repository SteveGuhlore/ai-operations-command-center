# Observation Ledger — Tony Eval Harness Build (2026-06-07)

Per MLE-workflow: one append-only log so each iteration makes the next easier.

## Ground truth established (from reading the real code/data)
- Verdicts n=103 but only 2 distinct `date`s (06-05/06-06) — the verdicts file is flushed each
  session (`flush_session`). Walk-forward MUST split on the **outcome** `resolved_date` (05-18→06-03),
  NOT verdict date, or there is no temporal spread.
- Outcomes n=50 (delayed labels: pick_date→resolved_date, return_pct, result).
- Realized ledger n=4 — ALL losses (Friday energy stop-cluster: FCX,FCX,SLB,SNAP). The realized
  (ground-truth) sample is far too thin to promote anything → the honest harness verdict for now is
  `insufficient_sample`. This is the point: the gate must REFUSE, loudly, not fabricate optimism.
- Live grading rule lives in `tony_scorecard._is_right` + `_matched_verdict` (range-join on symbol +
  verdict.date ∈ [pick_date, resolved_date], latest verdict). Harness reuses these verbatim →
  guarantees baseline reproduction.
- `_realized_block` (research_wave.py:195) already enforces realized-track discipline + small-sample
  guard in the learning loop. Harness mirrors it.
- conviction sizing already built INERT + gated by `TONY_CONVICTION_SIZING` (off/on/auto);
  `conviction_enabled()` auto-mode needs graded≥20 + calibration gap≥10. Harness = the missing proof.
- Existing eval: `evals/tony/run_eval.py` (thin grading-logic regression, 9 fixture cases). Extend the
  `evals/tony/` namespace; don't duplicate.

## Decisions / safe assumptions (operator away — log + proceed per kickoff)
- Eval v1 = replay RECORDED verdicts/outcomes only (handoff §9 recommendation). No LLM re-runs.
- R-multiple needs a stop; realized rows lack one → expectancy is reported BOTH as return-based
  (always available, realized `pct`) and R-based (subset where stop is recoverable from the matched
  verdict/outcome). Promotion keys off realized return expectancy + sample size.
- Drawdown threshold default 8% / 3-consec-loss as conservative placeholders; handoff says model from
  data later (T0.3). Flagged in the breaker so it's swappable.
- Phase-0 guard wiring ships behind OFF flags (default OFF) so live paper behavior is unchanged.

## Risks being tracked
- Thin realized sample → every promotion blocked (correct, honest, expected).
- Verdict-track calibration is noisy (2 dates) → reported with CIs, never used as promotion truth.
- Parallel agents create 4 leaf modules; integration wires them behind flags (I do the wiring).
