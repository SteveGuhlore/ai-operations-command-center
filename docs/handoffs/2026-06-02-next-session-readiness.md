# Next-Session Handoff — Tony Stocks Go-Live Sync

**For:** a fresh Command Center session (assume zero prior context).
**Date written:** 2026-06-02 (evening).
**Goal of next session:** confirm the trading-bot ⇄ Command Center loop works together end-to-end, then wait for market open. Most building is DONE; this is verification + sync, not new features.

---

## 0. What this system is (60-second context)
Two-layer stock loop. **Layer 1 = the trading bot** (separate `TradingBotAgentProject` repo): scans the market, scores picks, sets target/stop, and drops a daily markdown brief into `bridge/tony-stocks/YYYY-MM-DD.md` here. **Layer 2 = "Tony Stocks"** (this repo, agent `market_research_worker`, gemini-2.5-pro): ingests that brief, does deeper analysis (live financials, own technicals, macro regime, news), writes a structured verdict per pick (reaffirm/adjust/override/pass/close) to `tony_stocks_verdicts.json`, and trades his **own Alpaca paper account**. The bot reads his verdicts to adjust. Both learn off the shared environment.

Full contract for the bot side: **`docs/handoffs/2026-06-02-tony-loop-and-cockpit.md`** (read it). Build plan/history: `docs/superpowers/plans/2026-06-02-tony-stocks-phases.md`.

---

## 1. Status — what's built & VERIFIED (don't rebuild)
- ✅ Bridge ingestion: `runner/bridge/tony_bridge.py` reads the markdown bridge → spawns `TONY-DAILY-BRIEF` task. Verified live.
- ✅ Tony's analyst tools: `get_stock_data`, `get_price_history`, `get_market_regime`, `write_tony_verdict`, `write_tony_insight`, `log_tony_idea`. All registered + live-smoked.
- ✅ Learning: `runner/ledger/tony_scorecard.py` (range-join verdicts⇄outcomes, agreement matrix, calibration, edges) + weekly self-review. Degrades to `awaiting_outcomes` until the bot emits outcomes.
- ✅ Alpaca paper: `runner/ledger/alpaca_paper.py` — verdicts → paper orders in Tony's OWN account. Connection verified ($100k paper account, test order accepted). Keys in `.env`.
- ✅ Real-money guard: `runner/ledger/tony_live_guard.py` — DISABLED (paper only; real money gated).
- ✅ 303 tests pass (`python -m pytest tests/runner/ evals/ -q`). 8 commits on `master`.
- ✅ Quiet mode: outreach (Pitch) + Prospector pipeline PAUSED — only Tony runs.

## 2. What's LEFT (two buckets)

### A. Operator (Stephen) actions
- **Start the runner** (nothing fires until it runs): `pythonw scripts/launch.py --interval 600` (dashboard :8765 + 10-min cycle). Optionally install autostart: `powershell -File scripts/install-autostart.ps1` (the auto-classifier blocks Claude from doing this — operator must run it).
- **(Optional) enable fan-out** for deeper per-pick analysis: set env `TONY_FANOUT_MIN_TIER1=3` and `TONY_FANOUT_MAX=6`. Leave unset for a single combined daily brief.

### B. Trading-bot terminal (the other session) — confirm these are done
1. Keeps dropping the daily bridge `bridge/tony-stocks/YYYY-MM-DD.md` in the agreed format.
2. Emits **`reports/tony_stocks_outcomes.json`** with `pick_date` (first-appearance date) + `resolved_date` (range-join; `pick_id` optional). This unlocks Tony's learning.
3. **Reads `tony_stocks_verdicts.json`** to adjust its own picks (closes the loop).
4. Uses a **separate Alpaca paper account** from Tony (never shared keys).
5. Cockpit (`dashboard-web`, their repo) reads `tony_stocks_verdicts.json` + `tony_stocks_record.json`.

---

## 3. THE SYNC CHECKLIST (the main job for next session)
Run these to prove both sides work together. Do them with the operator + the bot terminal.

- [ ] **Runner up:** `launch.py` running; dashboard reachable at http://127.0.0.1:8765.
- [ ] **Bridge → task:** drop a fresh `bridge/tony-stocks/<today>.md` (or have the bot do it); within ~10 min a `TONY-DAILY-BRIEF-<date>` appears in `workspace/tasks/` and runs. (Force a one-off test by running `python -c "from runner.bridge.tony_bridge import scan_and_process; scan_and_process()"`.)
- [ ] **Verdict written:** after Tony runs, `../TradingBotAgentProject/reports/tony_stocks_verdicts.json` has entries (symbol, tony_score, scanner_score, verdict, thesis).
- [ ] **Record refreshes:** `tony_stocks_record.json` exists (status `awaiting_outcomes` until the bot sends outcomes — that's expected pre-open).
- [ ] **Paper book:** with market open, `alpaca_paper.sync()` runs in-cycle and Tony's Alpaca paper account shows positions matching his open verdicts. (Pre-open, orders queue.)
- [ ] **Outcomes round-trip (after first trades resolve):** bot writes `tony_stocks_outcomes.json`; `python -c "from runner.ledger.tony_scorecard import compute_record; print(compute_record())"` flips from `awaiting_outcomes` to `scored`, and the Cockpit's agreement matrix populates.
- [ ] **Bot reads verdicts:** confirm with the bot terminal that it ingests `tony_stocks_verdicts.json` and adjusts.

---

## 4. Health-check commands (a fresh session can paste these)
```bash
# tests green
python -m pytest tests/runner/ evals/ -q

# credentials live (Vertex + Brave + Alpaca paper)
python -c "from dotenv import load_dotenv; load_dotenv(); from runner.ledger.alpaca_paper import account_record; print('alpaca:', account_record().get('status'))"

# tools registered for Tony
python -c "import runner.main as m; print([t['name'] for t in m.ROLE_TOOLS['market_research_worker']])"

# scorecard state (awaiting_outcomes until bot sends outcomes)
python -c "from runner.ledger.tony_scorecard import compute_record; print(compute_record())"
```

## 5. Key files & envs
- Ingestion: `runner/bridge/tony_bridge.py` | Tools: `runner/tools/{stock_data,stock_technicals,market_regime,tony_verdict,tony_ideas}.py`
- Learning: `runner/ledger/tony_scorecard.py` | Paper: `runner/ledger/alpaca_paper.py` | Guard: `runner/ledger/tony_live_guard.py`
- Agent persona: `agents/market_research_worker.md` | Cycle wiring: `runner/main.py` (`run_cycle`)
- Envs: `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` (set, paper), `TONY_FANOUT_MIN_TIER1`/`TONY_FANOUT_MAX` (fan-out), `TONY_OUTCOMES_FILE`/`TONY_VERDICTS_FILE`/`TONY_RECORD_FILE` (override paths), `TONY_PAPER_NOTIONAL` (per-position $, default 1000).

## 6. Do NOT
- Don't un-pause outreach/Prospector (operator paused them; `OUTREACH_PAUSED=True`, runway paused).
- Don't enable real-money trading (the guard stays disabled; paper only).
- Don't rebuild the tools above — they're done and tested. This session is sync + verify.

**Bottom line:** code is done, committed, green; Alpaca verified. Next session = start the runner, run §3 with the bot terminal, then wait for open.
