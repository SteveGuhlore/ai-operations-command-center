# Spec — B1: Conviction-Weighted Sizing (Tony Stocks)

**Status:** BUILT 2026-06-05, shipped behind `TONY_CONVICTION_SIZING=off` (inert until flipped) +
the attribution metric live in `record.json`. 399 tests green. **Owner:** Command Center (CC) side.
**Depends on:** Tier-A enrichments (commit `5bb65bf`) — calibration is now surfaced in briefs.
**Locked decisions:** moderate curve · gate behind proven calibration · CC-only sizing + attribution metric.

---

## 1. Problem & intent
Today every Tony verdict risks the SAME 1% of equity regardless of his `confidence`
(low/medium/high). His conviction has no effect on how much money rides on a pick — so a
"high" call and a "low" call get identical position sizes. If his calibration is real (high
actually outperforms low — the exact metric `tony_outcomes`/`record.calibration` measures, now
shown in his briefs via A2), then tilting capital toward high-conviction names is +EV.

**B1 makes `confidence` scale the per-trade risk %, within the existing risk envelope.**

## 2. The measurement tension (why this touches the bot)
The head-to-head is currently *clean*: identical risk formula, only the reasoning differs, so
"Tony beats the bot" = "Tony's stock-picking is better." Once Tony sizes by conviction, his
equity reflects **picking edge + sizing edge combined**.

Resolution — **decompose, do NOT make the bot mirror conviction**:
- The bot stays flat-1% as the independent control group.
- We compute a pure attribution (no second account): picking alpha vs sizing alpha.

---

## 3. CC-side design

### 3.1 Sizing curve (locked: moderate)
| confidence | risk multiplier | effective risk % |
|---|---|---|
| low | 0.5× | 0.5% |
| medium | 1.0× | 1.0% (unchanged) |
| high | 1.5× | 1.5% |

Hard invariants — conviction scales the risk budget but **never breaches existing caps**:
- still capped by `MAX_NOTIONAL_PER_POSITION` ($10k/entry),
- `MAX_OPEN_POSITIONS=50`, `MAX_DAILY_ORDERS=200` unchanged,
- unknown/missing confidence → 1.0× (today's behavior).

### 3.2 Config (new env, all defaulted to today's behavior)
```
TONY_CONVICTION_SIZING        = "off"        # off | on | auto   (default off)
TONY_CONV_MULT_LOW            = 0.5
TONY_CONV_MULT_MEDIUM         = 1.0
TONY_CONV_MULT_HIGH           = 1.5
TONY_CONV_MIN_GRADED          = 20           # auto-gate: need this many graded picks
TONY_CONV_MIN_CAL_GAP         = 10.0         # auto-gate: high_win_rate - low_win_rate >= this
```

### 3.3 Gating (locked: gate behind proven calibration)
`conviction_enabled()` in `alpaca_paper`:
- `"off"` → always 1.0× (flat). **This is the default; B1 is inert until flipped.**
- `"on"`  → always apply the curve (manual override once we trust it).
- `"auto"`→ apply the curve **only if** `record.graded >= TONY_CONV_MIN_GRADED`
  **and** `calibration.high` and `calibration.low` are both present
  **and** `calibration.high - calibration.low >= TONY_CONV_MIN_CAL_GAP`.
  Reads the already-written `record.json` (`tony_scorecard.compute_record()`), so no new data.

Today `graded≈1`, so `auto` is a no-op until the record matures — exactly the safety we want.

### 3.4 Code changes (small, localized to `runner/ledger/alpaca_paper.py`)
1. `plan_orders(...)` — carry `confidence` from each verdict into the emitted buy action dict.
2. `conviction_multiplier(confidence) -> float` — pure; maps via the env multipliers; 1.0 fallback.
3. `conviction_enabled() -> bool` — the gate in 3.3 (reads `compute_record()`), fail-safe to False.
4. `_Broker.buy(...)` — when enabled, `risk_pct = RISK_PCT * conviction_multiplier(conf)` before
   `risk_based_qty(...)`. The `max_notional` cap stays as-is, so high-conviction can't exceed the
   per-position ceiling. When disabled, behavior is byte-for-byte today's.

No change to the verdict schema (`confidence` already exists), the execution mechanics, the
protection/reprice/close paths, or the portfolio caps.

---

## 4. Honest measurement — attribution metric (pure analytics)
New `sizing_attribution()` in `tony_scorecard` (reuses the existing range-join helpers):
- `flat_return = mean(return_pct_i)` over resolved picks (sizing-independent).
- `weight_i = conviction_multiplier(verdict_i.confidence)`.
- `conviction_return = Σ(weight_i · return_pct_i) / Σ weight_i`.
- **`sizing_alpha = conviction_return − flat_return`** → the sizing policy's standalone contribution.

Surfacing:
- add optional block to `record.json` (`write_record`):
  `sizing_attribution: {conviction_return_pct, flat_return_pct, sizing_alpha_pct, graded}`.
- once `graded` is meaningful, add one line to `track_record_block()` so Tony sees whether his
  conviction sizing is actually adding alpha.

This is computable from `verdicts.confidence` + `outcomes.return_pct` alone — no second account,
cheap, and it lets the "Shadow-only first" rollout be measured before any real tilt.

---

## 5. Bot-side coordination contract (hand this section to the bot session)
B1 is **CC-only**, but three things on the bot side must hold or the experiment breaks:

1. **The bot's sizing MUST remain flat-1%.** Do **not** add conviction sizing to the bot to
   "match" Tony — the bot is the control group. Mirroring it deletes the baseline and makes the
   picking-vs-sizing decomposition unrecoverable.
2. **`record.json` gains an optional `sizing_attribution` object.** The bot's record /
   `CommandCenterAgreement` reader must **tolerate the new key** (additive; ignore if unknown) —
   no strict-schema rejection.
3. **Parity doc amendment.** `execution-parity.md` (both repos' copies) changes from
   *"identical risk formula"* to: *"Tony's risk % is conviction-scaled (0.5/1.0/1.5×, gated on
   proven calibration); the bot stays flat-1% as the control; the head-to-head is reported as
   picking alpha vs sizing alpha."* Agree the wording on both sides before flipping the gate `on`.

Not in scope (declined): the bot consuming Tony's conviction for its own research prioritization.

---

## 6. Tests to add (`tests/runner/`)
- `conviction_multiplier`: low/medium/high/unknown → 0.5/1.0/1.5/1.0.
- `conviction_enabled`: off→False; on→True; auto with graded<20→False; auto with gap<10→False;
  auto with graded≥20 & high−low≥10→True.
- `buy()` integration (mock broker): high-conviction qty ≈ 1.5× medium at the same price/stop,
  but never exceeds `MAX_NOTIONAL_PER_POSITION`; disabled path == today's qty exactly.
- `sizing_attribution`: known verdicts+outcomes → expected flat/conviction/alpha numbers.
- regression: full suite stays green with the flag default `off`.

## 7. Rollout sequence
1. Ship behind `TONY_CONVICTION_SIZING=off` + the attribution metric (zero behavior change).
2. Run **shadow** for a few weeks: watch `sizing_alpha_pct` populate as picks resolve.
3. When `graded ≥ 20` and `high − low ≥ 10` and shadow `sizing_alpha` is positive, flip to
   `auto` (or `on`) — after the bot session has accepted §5.
4. Restart the runner (cached modules; see runner-restart gotcha).

## 8. Risks & guardrails
- **Sizing on noise:** mitigated by the calibration gate (§3.3) — inert until proven.
- **Drawdown amplification:** bounded by the per-position notional cap and the modest 1.5× top.
- **Metric confusion:** mitigated by the attribution split (§4) — picking vs sizing always separable.
- **Tandem drift:** the bot accidentally adopting conviction sizing — covered explicitly in §5.1.
