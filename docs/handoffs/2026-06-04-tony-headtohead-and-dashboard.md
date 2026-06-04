# Next-Session Handoff — Tony Stocks head-to-head + dashboard

**For:** a fresh Command Center session (assume zero prior context).
**Date written:** 2026-06-04 (after the 16:00 close).
**One-line status:** The bot⇄Tony head-to-head is **live, fair, and fully instrumented** — equal *rules*, different *reasoning*; Tony now sizes entries at **$10k** (1% of his $1M) to match the bot's 1%-per-position on its $100k; the CC dashboard shows a clean Paper Book, a "Tony's Calls" divergence view (paged), and a normalized + backfilled head-to-head equity curve. All committed on `master`. Everything below is done unless under **Open items**.

---

## 0. What this system is (60-second context)
Two separate repos under `C:\Users\alexa\Downloads\`:
- **The bot** (`TradingBotAgentProject`): scans a ~548-symbol universe, trades its **own $100k** Alpaca paper account, and drops markdown **bridges** into this repo's `bridge/tony-stocks/` at ~09:30 / 10:30 / 13:00 / 15:30 / 16:00 (EOD).
- **Tony / "Command Center"** (this repo, agent `market_research_worker`, gemini-2.5-pro): ingests each bridge, does an **independent deep-dive** (fundamentals, news, analyst targets, earnings via `get_stock_data`/`get_price_history`/`web_research`), writes structured **verdicts**, and trades his **own $1M** Alpaca paper account (key ends `…K5ZP`). The bot reads Tony's verdicts for the record only — **never acts on Tony's book** (pure separation; accounts never share keys).
- The experiment: *does the second (reasoning) pass make money?* Compared on **%-returns** (see §2).

Prior handoff: `docs/handoffs/2026-06-03-tony-live-trading-handoff.md`. Parity contract (bot side): `../TradingBotAgentProject/docs/CONTRACTS/execution-parity.md`.

---

## 1. What shipped today (all committed on `master`)
- **Overnight protection** (`c80198d`): bracket buys are **GTC** so the stop/target legs survive the 16:00 close; reconciler re-attaches a GTC OCO to any naked whole-share position each task cycle. Also mirrors `write_record()` to `vault/tony-stocks/tony_stocks_record.json`.
- **Reprice on intraday adjust** (`ada63fa`, `dd78c6d`, `5eb6958`): an `adjust` re-prices the live OCO (cancel+replace), retrying through Alpaca's async cancel-settle; works for carried positions too.
- **No-pyramiding guard** (`20f05f8`): a held name isn't re-bought (the 09:25 reset clears the executed-log but never closes positions).
- **Pre-open deep-dive** (`dabcc7e`) + **deep-dive at every handoff** (`d797bb6`) + **per-ticker fan-out** (`d6bde67`, env `TONY_FANOUT_MIN_TIER1=3`) + **verdict-write lock** (`d6bde67`, race that dropped 22/24 verdicts).
- **Head-to-head sizing parity** (`f95365c` → `932f14c`): Tony sizes via `risk_based_qty` (1% risk, **$10k** notional cap = 1% of his $1M), `max_open_positions=50`, `max_daily_orders=200`. The bot is **$1k/position** on its $100k (also 1%). See [[project_tony_head_to_head_parity]] memory.
- **Dashboard** (`0c1ed5c`, `48cac03`, `fbab4df`, `a30aeb2`, `0d16bec`, `cbde52d`, `8abfcfe`): normalized equity curve (indexed to starting capital, backfilled from Alpaca portfolio history + bot mark-to-market on historical bars, axis-labelled); Paper Book = one row/position (Sym·Qty·Entry·Price·Target·Stop·P/L); live metrics; **Tony's Calls** = bot→Tony divergence + thesis + evidence, **paged 10/mini-page**; Sector Clusters removed.

Tests: **340+ green** (`python -m pytest tests/runner/ evals/ -q`).

---

## 2. The parity rules (what's SAME vs DIFFERENT) — do not break
**Accounts are UNEQUAL on purpose:** Tony **$1M**, bot **$100k**. Compare on **%-returns**, not absolute $.
- **SAME:** risk formula (`risk_based_qty`), `risk_per_trade_pct=1.0`, max positions 50, max daily orders 200, GTC bracket mechanics, the candidate universe (Tony acts on the bot's bridge, which already passed the bot's `min_risk_reward=1.5` gate), costs, grading.
- **Per-entry notional is account-scaled:** Tony **$10k** (`TONY_MAX_NOTIONAL_PER_POSITION=10000`), bot **$1k** — both 1% of their own equity.
- **DIFFERENT (the experiment):** reasoning (technical algo vs LLM research), tools/data, the decision (reaffirm/adjust/override/pass/close), and the resulting stop/target levels.
- **Do NOT** revert Tony to the old flat `$1000 TONY_PAPER_NOTIONAL`. Positions opened before the $10k change (the original $1k buys) are **left to run** to target/stop/close — clean head-to-head P&L starts from entries after the change.

---

## 3. LIVE STATE (verify first)
- **Runner + dashboard:** `python scripts/launch.py --interval 180` (detached, hidden). Find PID: `Get-NetTCPConnection -LocalPort 8765 -State Listen`. Dashboard: http://127.0.0.1:8765 (remote: https://alexandria.tail0ae2dc.ts.net).
- **Bot:** `trading_bot.cli watch` + API on :8001 (drops bridges, exposes `/api/paper/positions` used by the equity backfill).
- **Pre-open reset:** Windows task `TonyPreOpenReset` weekdays 09:25 ET → `scripts/preopen_reset.py` (cancels only unfilled entries, **keeps** protective legs; clears verdicts+executed-log; queues the pre-open deep-dive).
- **Standing at close 2026-06-04:** Tony equity ~$1,000,125 (**+0.01%**); bot ~+1.44% (Tony's early $1k positions barely moved his $1M — the $10k entries fix this going forward). 11 Tony positions, all GTC-protected.
- **⚠ Runner caches Python modules at launch — any `runner/**` edit needs a runner RESTART** (kill launcher + port-8765 child, relaunch).

---

## 4. OPEN ITEMS / watch
1. **Tomorrow's open is the first clean head-to-head** — Tony's $10k entries vs the bot's $1k, both 1%/position. Watch the equity curve diverge with real shape (it backfills today's session on start; live snapshots append each cycle).
2. **Equity backfill is one-shot on demand** — `equity_history.backfill()` was run manually to seed history. If `workspace/equity-history.json` is wiped, re-run it. (It's NOT auto-run in the cycle; only `snapshot()` is.)
3. **Bot funnel** (bot side, other session): enabled + committed (`ab038be`) but activates on the bot's next watch-loop restart — not a CC concern.
4. **Signal-ledger prose metrics** are no longer shown (top cards now derive from the live book); the `/api/tony/stocks` ledger panel still renders below and can lag.

---

## 5. Health-check commands
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen     # runner/dashboard up
Get-ScheduledTaskInfo TonyPreOpenReset                 # reset armed (LastTaskResult 0)
```
```bash
python -m pytest tests/runner/ evals/ -q               # tests green (340+)
python -c "from dotenv import load_dotenv; load_dotenv(); from runner.ledger.alpaca_paper import paper_book; print(paper_book()['equity'])"
# dashboard endpoints
curl -s http://127.0.0.1:8765/api/tony/book | head -c 300
curl -s http://127.0.0.1:8765/api/tony/equity-curve | head -c 300
```

## 6. Key files
- Sizing/orders/protection: `runner/ledger/alpaca_paper.py` (`risk_based_qty`, `plan_orders` max_new_buys, `plan_reprices`, broker `buy`/`protect`/`reprice`/`cancel_entry_orders`, `_reconcile_protection`).
- Equity curve: `runner/ledger/equity_history.py` (`snapshot`/`curve`/`backfill`, indexed to start capital) → `GET /api/tony/equity-curve`.
- Bridge → tasks: `runner/bridge/tony_bridge.py` (`_make_brief_from_bridge` daily / `_make_intraday_brief` deep intraday / `make_preopen_deepdive` / fan-out).
- Verdict tool: `runner/tools/tony_verdict.py` (target>stop guard + write lock).
- Dashboard: `dashboard/server.py` (`/api/tony/book` enriched with bot levels, `/api/tony/equity-curve`) + `dashboard/index.html` (Paper Book, Tony's Calls paged, equity chart).
- Reset CLI: `scripts/preopen_reset.py`.

## 7. Do NOT
- Don't revert Tony to flat `$1000` sizing, or change one book's risk params without the other.
- Don't share Alpaca keys between bot and Tony.
- Don't edit `runner/**` and expect it live without a runner restart.
- Don't re-introduce the broken-data narrative into `signal-ledger.md` (it anchors Tony into not trading).

**Bottom line:** the experiment is fair and instrumented; the first clean apples-to-apples day is the next open. 🚀
