# Execution Parity Contract — Command Center (CC) mirror

**Status:** v1.1 mirror (2026-06-05). **Canonical source:** the bot repo's
`../TradingBotAgentProject/docs/CONTRACTS/execution-parity.md` (the bot's `paper_trading`
config is the reference; CC matches it). This file is the **CC-side mirror** so the contract
is, per §B.1's gate rule, *"mirrored on both sides."* It also resolves the
`docs/CONTRACTS/execution-parity.md` reference in `runner/ledger/alpaca_paper.py`.

The head-to-head is valid only with **one independent variable** (the brain). Execution, risk,
and grading are held identical; only how each side *decides* differs.

---

## A. Section-A conformance (CC matches the canonical values) ✅

| Parameter | Canonical (bot) | CC value | Where in CC |
|---|---|---|---|
| Risk per trade | `1.0%` | `RISK_PCT = 1.0` | `runner/ledger/alpaca_paper.py` |
| Sizing formula | `floor(risk$ ÷ (entry−stop))`, capped by max-notional | `risk_based_qty()` | same |
| Max open positions | `50` | `MAX_OPEN_POSITIONS = 50` | same |
| Max notional / position | 1% of equity → CC ($1M) = `10000` | `MAX_NOTIONAL_PER_POSITION = 10000` | same |
| Max daily orders | `200` | `MAX_DAILY_ORDERS = 200` | same |
| Order mechanics | market entry + **GTC** OCO bracket | GTC bracket on entry, GTC OCO on reconcile | `_Broker.buy` / `_reconcile_protection` |
| Comparison basis | %-return, equity indexed to 100 | `equity_history.indexed_curve()` | `runner/ledger/equity_history.py` |

**Note:** Tony moving a stop changes his share count at the *same* 1% risk — that is the
intended divergence (his level, identical formula), not a parity violation.

---

## B.1 — CC obligations for the conviction-sizing experiment (BUILT)

CC implements B1 entirely in **Tony's book**; the bot is untouched and stays the flat-1%
control. CC confirms it meets the three §B.1 requirements:

1. **Conviction lives only in Tony's book.** `confidence` → risk multiplier
   (low/med/high = 0.5/1.0/1.5×) in `alpaca_paper.conviction_multiplier`, applied in
   `_Broker.buy` via a `risk_pct` override. The `MAX_NOTIONAL` cap still binds, so a
   high-conviction trade never exceeds the 1%-of-equity single-name cap. The bot has, and
   must keep, **no** conviction term (their guard test `tests/test_b1_control_parity.py`).
2. **Additive `sizing_attribution` in `record.json`.** `tony_scorecard.write_record()` adds an
   optional `sizing_attribution` object — **picking/sizing-alpha split** in the contract's
   vocabulary:
   `{"status","graded","picking_alpha_pct","conviction_return_pct","sizing_alpha_pct"}`
   (`flat_return_pct` alias retained). It is additive only; the bot ignores unknown keys.
3. **Picking-alpha vs sizing-alpha reported separately.** `sizing_attribution()` decomposes
   realized return (sizing-independent %) into `picking_alpha_pct` (equal-weight selection
   quality, comparable to the bot) and `sizing_alpha_pct` (extra return from conviction
   weighting). No second account — pure analytics over `verdicts.confidence × outcomes.return_pct`.

**Gate (CC side):** B1 ships **inert** — `TONY_CONVICTION_SIZING=off` by default (flat 1%,
byte-for-byte the B0 baseline). It is flipped to `auto`/`on` only when **all** hold:
- this contract is mirrored on both sides ✅ (this file + the bot's canonical),
- CC emits `sizing_attribution` with the picking/sizing split ✅,
- the record proves calibration (`graded ≥ 20` AND high-confidence win-rate − low ≥ 10pts),
- and shadow `sizing_alpha_pct` is positive.

Section A stays frozen unless both books change together.

**See also:** CC spec `docs/superpowers/specs/2026-06-05-b1-conviction-sizing.md`.
