# Spec — Phase 3 Engine Moonshots (Track 5, engine-side only)

**Date:** 2026-06-07 · **Status:** SPEC ONLY (no behavior). Gated behind Phase 1 passing the eval
harness. Marketing-flavored moonshots (AI voice/video persona, live reasoning feed) stay PARKED with
the marketing tracks. Each moonshot earns its place only by improving the harness's out-of-sample
metrics.

---

## T5.1 — Multi-agent trading council
**Idea:** specialist sub-agents (Bull, Bear, Risk, Macro) debate each pick to a consensus verdict —
deeper reasoning AND transparency material ("watch the analysts argue").

**Design direction (recorded-replay first, like the harness):**
- Council = a function `deliberate(symbol, context) -> {verdict, confidence, dissent[]}`. Each role is
  a prompt persona over the SAME data tools Tony already has (`get_stock_data`, `get_catalysts`,
  `get_market_regime`, sanitized news via `external_data_guard`). Risk seat holds a hard veto wired to
  the code-enforced guards (`drawdown_breaker`, `cluster_risk`) — the LLM cannot override a halt.
- Output maps to the EXISTING `write_tony_verdict` contract (tony_score/confidence/verdict/evidence)
  so nothing downstream changes — the council is a richer *decider*, same interface.
- **Gate it with the harness:** the council is a candidate change. Run `evaluate_candidate` over the
  recorded set; it ships only if pooled OOS expectancy improves with no guardrail regression.
- Cost: low-frequency, so run the seats on `gemini-2.5-pro` (Vertex $300 credit, T1.10).
- Transparency artifact: persist each seat's argument to the decision audit log → great content later.

**Build order:** seats as personas → consensus aggregator → Risk veto wired to guards → harness A/B vs
single-agent Tony → ship behind `TONY_COUNCIL_ENABLED` (default off) only on a green candidate gate.

## T5.2 — Self-improving RL memory (extends T1.7)
**Idea:** move from hand-written rules toward a *learned* memory policy (Letta/MemGPT-style) so Tony
optimizes what to remember/retrieve/forget.

**Design direction:**
- Build on `experience_memory`: it already has the confidence/decay/quarantine/retrieval primitives.
  RL layer learns the POLICY parameters (promote/retire thresholds, decay half-life, retrieval-k,
  relevance weights) instead of fixing them by env.
- **Reward = the harness.** The objective is out-of-sample expectancy on the realized track; the
  policy search (start with bandit/grid over the threshold params, not deep RL) is scored by replaying
  recorded history through `harness.evaluate_candidate`. Cheap, offline, no live risk.
- Fail-closed: a learned policy promotes only if it beats the hand-tuned defaults on the harness.
- Anti-forgetting stays load-bearing — the policy may not retire a rule the realized track still
  supports.

**Build order:** parameterize `experience_memory` thresholds → offline policy search scored by the
harness → adopt only harness-proven params → optional online adaptation behind a flag.

## T5.3 — Options / asset-class expansion (sequenced LAST)
**Idea:** extend beyond equities to options (and/or short selling). Higher complexity + risk +
compliance weight — only after the equity engine is proven profitable on real money.

**Design direction (spec only — confirm operator appetite first):**
- New data contract: options chains, IV/Greeks, expiry/strike as part of the entity grain. The eval
  harness must be extended to grade defined-risk structures (max-loss known) before any order.
- Risk model differs fundamentally (theta decay, assignment, defined vs undefined risk) — the
  `drawdown_breaker` and sizing must be re-derived for options; do NOT reuse equity sizing.
- Compliance: options approval tiers + suitability; another hard legal gate.
- **Gate:** equities proven profitable on real money for a meaningful window FIRST. This is explicitly
  last in the program.

---

## Cross-cutting
- Everything here is a **candidate** for the eval harness; nothing ships on intuition.
- Every guard (breaker, cluster cap, sizing, audit, account isolation) applies unchanged.
- Default-OFF flags throughout; operator-deploy only.
