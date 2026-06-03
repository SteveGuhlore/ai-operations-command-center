# Tony Stocks Phases 2–6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Evolve Tony Stocks from "independent analyst" (Phase 1, shipped) into a self-calibrating, portfolio-aware, learning second-layer agent — building every Command-Center-side piece now, degrading gracefully where the trading-bot outcomes feed isn't wired yet.

**Architecture:** Each capability is a small focused tool in `runner/tools/` registered in `tool_runner.py` and exposed to `market_research_worker` in `main.py`. Learning/scorecard logic is pure functions over the verdicts/outcomes JSON contracts (easy to unit-test). Scheduled cadences reuse `runner/scheduler/daily_jobs.py`. Real-money stays a disabled, documented guard.

**Tech Stack:** Python 3.x, yfinance (financials/technicals/macro), pytest, existing runner tool/registry pattern.

**Dependency note:** Phase 3 learning and Phase 4 calibration need `tony_stocks_outcomes.json` from the trading bot (see `docs/handoffs/2026-06-02-tony-loop-and-cockpit.md` §4). The engines are built now and read that file if present; absent it, they return "awaiting outcomes" rather than failing.

---

## File structure

| File | Responsibility |
|---|---|
| `runner/tools/stock_technicals.py` (new) | `get_price_history` — OHLC + RSI/SMA/ATR/volume-trend (Phase 2) |
| `runner/tools/tony_verdict.py` (modify) | enforce target/stop on adjust/override (Phase 2) |
| `runner/bridge/tony_bridge.py` (modify) | per-Tier-1 fan-out option (Phase 2) |
| `runner/tools/market_regime.py` (new) | `get_market_regime` — VIX/SPY/sector RS → risk on/off (Phase 4) |
| `runner/ledger/tony_scorecard.py` (new) | join verdicts⇄outcomes, grade, agreement matrix, record (Phase 3) |
| `runner/scheduler/daily_jobs.py` (modify) | weekly `tony_self_review` cadence (Phase 3) |
| `runner/main.py` (modify) | spawn self-review task; register new tools (Phase 3/4) |
| `runner/tools/tony_ideas.py` (new) | `log_tony_idea` — self-originated picks (Phase 5) |
| `runner/ledger/tony_live_guard.py` (new) | disabled real-money gate + kill switch (Phase 6) |
| `tests/runner/test_*.py` | one test module per unit above |
| `evals/tony/` (new) | fixture picks + eval runner (cross-cutting) |

---

## Phase 2 — Depth & reliability

### Task 1: Technical-analysis tool (`get_price_history`)

**Files:**
- Create: `runner/tools/stock_technicals.py`
- Modify: `runner/agents/tool_runner.py`, `runner/main.py`
- Test: `tests/runner/test_stock_technicals.py`

- [ ] **Step 1: Write the failing test**
```python
from runner.tools import stock_technicals as st

def test_indicators_from_synthetic_closes(monkeypatch):
    closes = [10 + (i % 5) for i in range(60)]
    highs = [c + 1 for c in closes]; lows = [c - 1 for c in closes]
    vols = [1000 + i for i in range(60)]
    monkeypatch.setattr(st, "_fetch_ohlcv", lambda sym, days: {
        "close": closes, "high": highs, "low": lows, "volume": vols})
    r = st.get_price_history("TEST", days=60)
    assert r["symbol"] == "TEST"
    assert 0 <= r["rsi14"] <= 100
    assert r["sma20"] is not None and r["sma50"] is not None
    assert r["atr14"] > 0
    assert r["volume_trend"] in ("rising", "falling", "flat")
```

- [ ] **Step 2: Run test to verify it fails** — `python -m pytest tests/runner/test_stock_technicals.py -v` → FAIL

- [ ] **Step 3: Implement `stock_technicals.py`** (pure math split from network fetch; see Task code in design — `_fetch_ohlcv` via yfinance `.history`; `_sma/_rsi/_atr/_vol_trend`; `get_price_history` returns symbol,last,rsi14,sma20,sma50,atr14,pct_from_52w_high,pct_above_sma50,volume_trend; TOOL_SPEC name `get_price_history`).

- [ ] **Step 4: Register + expose** — `tool_runner.py`: import + `register_tool("get_price_history", get_price_history)`; `main.py`: import `TOOL_SPEC as PRICE_HIST_TOOL_SPEC` + add to `ROLE_TOOLS["market_research_worker"]`.

- [ ] **Step 5: Run tests** → PASS

- [ ] **Step 6: Commit** `feat(tony): get_price_history technical tool`

### Task 2: Target/stop discipline on verdicts

**Files:** Modify `runner/tools/tony_verdict.py`; Test `tests/runner/test_tony_verdict.py`

- [ ] **Step 1: Failing test**
```python
from runner.tools import tony_verdict as tv
def test_override_requires_target_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    r = tv.write_tony_verdict(symbol="X", tony_score=40, verdict="override", thesis="t")
    assert "error" in r and "target" in r["error"].lower()
def test_reaffirm_allows_blank_target(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "VERDICTS_FILE", tmp_path / "v.json")
    assert tv.write_tony_verdict(symbol="X", tony_score=80, verdict="reaffirm", thesis="t").get("success")
```
- [ ] **Step 2: Verify fails**
- [ ] **Step 3: Add validation** after verdict-enum check:
```python
    if v in ("adjust", "override") and (target is None or stop is None):
        return {"error": f"verdict '{v}' requires both target and stop (your own levels)"}
```
- [ ] **Step 4: Tests pass**
- [ ] **Step 5: Commit** `feat(tony): require target/stop on adjust|override verdicts`

### Task 3: Per-Tier-1 fan-out

**Files:** Modify `runner/bridge/tony_bridge.py`; Test `tests/runner/test_tony_bridge.py`

- [ ] **Step 1: Failing test** — fan-out spawns a child task per Tier-1 symbol when `FANOUT_MIN_TIER1` met.
- [ ] **Step 2: Verify fails**
- [ ] **Step 3: Implement** — `FANOUT_MIN_TIER1 = int(os.environ.get("TONY_FANOUT_MIN_TIER1","0"))`; `_extract_tier1_symbols(md)` regex `\[\[([A-Z][A-Z0-9.\-]{0,9})\]\]` between "Tier 1" and "Tier 2"; `_spawn_ticker_task(date,sym)` writes `TONY-TKR-<sym>-<date>.md` (task_type `ticker_deepdive`, market_research_worker) instructing get_stock_data+get_price_history+web_research+write_tony_verdict for that one symbol; in `_make_brief_from_bridge`, if `FANOUT_MIN_TIER1` and len(syms)>=threshold, spawn per symbol.
- [ ] **Step 4: Tests pass** (full `test_tony_bridge.py`)
- [ ] **Step 5: Commit** `feat(tony): optional per-Tier-1 fan-out for deep verdicts`

---

## Phase 3 — Learning loop (engine now; data from bot)

### Task 4: Scorecard engine

**Files:** Create `runner/ledger/tony_scorecard.py`; Test `tests/runner/test_tony_scorecard.py`

- [ ] **Step 1: Failing test** — join (symbol, pick_date==verdict date), grade, agreement matrix; `awaiting_outcomes` when no outcomes file.
- [ ] **Step 2: Verify fails**
- [ ] **Step 3: Implement** — `VERDICTS_FILE/OUTCOMES_FILE/RECORD_FILE` env-overridable; grading rule: bullish (reaffirm/adjust) right iff return_pct>0; non-bullish (override/pass/close) right iff return_pct<=0; agreement matrix {agreed_right, agreed_wrong, override_saved, override_missed}; `compute_record()` + `write_record()` → `tony_stocks_record.json`.
- [ ] **Step 4: Tests pass**
- [ ] **Step 5: Commit** `feat(tony): scorecard engine — grade verdicts vs outcomes`

### Task 5: Weekly self-review cadence

**Files:** Modify `runner/scheduler/daily_jobs.py`, `runner/main.py`; Test `tests/runner/test_tony_self_review.py`

- [ ] **Step 1: Failing test** — `_maybe_run_tony_self_review` spawns `tony_self_review` task when `self_review_due()` and record graded>=3.
- [ ] **Step 2: Verify fails**
- [ ] **Step 3: Implement** — `self_review_due()/mark_self_review_ran()` (7-day state, mirror scout cadence) in daily_jobs; `_maybe_run_tony_self_review()` in main reads compute_record, spawns review task only when scored & graded>=3; call it in `run_cycle()`.
- [ ] **Step 4: Tests pass**
- [ ] **Step 5: Commit** `feat(tony): weekly self-review learning cadence`

---

## Phase 4 — Calibration & portfolio

### Task 6: Market-regime tool

**Files:** Create `runner/tools/market_regime.py`; register+expose; Test `tests/runner/test_market_regime.py`
- [ ] **Steps 1–5:** TDD `get_market_regime()` — `_fetch()` pulls ^VIX + SPY + sector ETFs (yfinance); classify VIX<18 & SPY>SMA50→risk_on, VIX>27 or SPY<SMA50→risk_off, else neutral; returns {regime,vix,leaders,laggards}. Register + add to Tony tools + prompt ("risk_off → downgrade conviction one tier"). Commit `feat(tony): market-regime macro tool`.

### Task 7: Confidence calibration

**Files:** Modify `runner/ledger/tony_scorecard.py`; extend `test_tony_scorecard.py`
- [ ] **Steps 1–5:** Extend `compute_record` with `calibration` = win-rate per confidence bucket (low/medium/high). Commit `feat(tony): confidence calibration in scorecard`.

---

## Phase 5 — Self-directed analyst

### Task 8: Self-originated idea channel

**Files:** Create `runner/tools/tony_ideas.py`; register+expose; Test `tests/runner/test_tony_ideas.py`
- [ ] **Steps 1–5:** `log_tony_idea(symbol, thesis, source, score, catalysts)` → `tony_stocks_ideas.json` (date,symbol,thesis,source∈{sector_theme,earnings_drift,own_pattern},score,status). Prompt note to log names the scanner missed. Commit `feat(tony): self-originated idea channel`.

### Task 9: Pattern-edge discovery

**Files:** Modify `runner/ledger/tony_scorecard.py`; extend suite
- [ ] **Steps 1–5:** `discover_edges()` mines graded verdicts for evidence-tag→win-rate combos with n≥5; returns top edges or `{"status":"insufficient_history"}`; fed into self-review body. Commit `feat(tony): pattern-edge discovery`.

---

## Phase 6 — Real-money readiness (governance only, DISABLED)

### Task 10: Live-trading guard (no execution)

**Files:** Create `runner/ledger/tony_live_guard.py`; Test `tests/runner/test_tony_live_guard.py`
- [ ] **Step 1: Failing test**
```python
from runner.ledger import tony_live_guard as g
def test_live_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TONY_LIVE_ENABLED", raising=False)
    assert g.live_allowed({"tony_win_rate": 99, "graded": 100})["allowed"] is False
def test_live_requires_enable_and_track_record(monkeypatch):
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    assert g.live_allowed({"tony_win_rate": 50, "graded": 10})["allowed"] is False
    assert g.live_allowed({"tony_win_rate": 62, "graded": 60})["allowed"] is True
```
- [ ] **Step 2: Verify fails**
- [ ] **Step 3: Implement** — `live_allowed(record)` allowed only if env `TONY_LIVE_ENABLED` set AND graded>=50 AND tony_win_rate>=60 AND no kill-switch file. No order code; documented gate.
- [ ] **Step 4: Tests pass**
- [ ] **Step 5: Commit** `feat(tony): disabled real-money governance gate`

---

## Cross-cutting — Eval harness

### Task 11: Verdict-logic regression eval

**Files:** Create `evals/tony/fixtures.json`, `evals/tony/run_eval.py`; Test `tests/runner/test_tony_eval.py`
- [ ] **Steps 1–5:** Fixtures = (verdict, outcome) cases with expected grade; `run_eval.py` replays through the scorecard grading rule headless (no network) and asserts stable math; test invokes it. Guards future prompt/tool changes. Commit `feat(tony): verdict-logic regression eval harness`.

---

## Self-review (plan vs roadmap)
- Phase 2 → Tasks 1–3 ✅; Phase 3 → 4–5 ✅ (grades when bot outcomes land); Phase 4 → 6–7 ✅; Phase 5 → 8–9 ✅ (backtest deferred — needs stored bridge corpus); Phase 6 → 10 ✅ disabled gate; Eval → 11 ✅.
- Cross-project dependency (outcomes feed) in handoff §4; engines degrade gracefully.
- **Deferred (explicit):** historical backtest replay (needs bridge corpus) and live order execution (out of scope).
