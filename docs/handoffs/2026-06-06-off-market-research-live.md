# Next-Session Handoff — Off-Market Research Engine is LIVE + finish the cadence

**Written:** 2026-06-06 (Sat) ~20:20 ET. **For:** a fresh Command Center session.
**State:** Feature merged to `master` (`875f616`), **runner restarted and live on :8765**, and the first
off-market wave is already staged: **93 tasks for the 2026-06-08 (Mon) open**.

---

## 0. 60-second context
Two layers, only two: **the bot** (`TradingBotAgentProject`, quant scanner, $100k Alpaca paper, drops
markdown bridges into `bridge/tony-stocks/`) and **Tony** (this repo, `market_research_worker` on
gemini-2.5-pro, $1M Alpaca paper, independent 2nd-pass). Everything Tony does is done by that ONE agent
— no new runtime agent personas. Golden rule: one-way file hand-offs. Alerts → Telegram.

This session built the **Off-Market Research Engine + 3 execution/recap fixes**. Spec:
`docs/superpowers/specs/2026-06-06-tony-off-market-research-engine-design.md`.

---

## 1. What shipped (on master, newest first)
- `343ace4` fix: defer un-priced exits (never lose a stop-out from the realized ledger) + repair the
  tandem sandbox (mock broker `buy()` was missing `risk_pct` since the B1 change; pin
  `TONY_MARKET_SESSION=open` for the mechanics step; redirect the realized writer into the sandbox).
- `5af2d2a` **C** — ranked candidate queue + open re-check gate (`runner/ledger/research_queue.py`,
  wired in `scripts/preopen_reset.py`). `workspace/research-queue.json`; the open re-validates top-N
  vs FRESH price and **never executes a stale queue price**.
- `30ad6dd` **B** — off-market orchestrator + budget lane (`runner/bridge/research_wave.py`, hook in
  `runner/main.py` idle branch, `runner/ledger/budget.py`).
- `e4ff9f9` **D** — realized-trade ledger + P/L recap (`runner/ledger/tony_realized.py`; `_notify_closed`
  records exits; recap in `main.py`).
- `70612a2` **A** — market-session clock + closed-market entry gate (`runner/ledger/market_clock.py`;
  gate in `alpaca_paper.sync()`).

**The three bugs that triggered this, now fixed:**
1. **Saturday entries (CARR/KDP):** `sync()` now blocks `buy` when `market_session()=="closed"`
   (no submit / no executed-log key / no alert). `close`/`reprice`/`protect`/reconcile still run.
2. **"1 graded" despite stop-outs:** Tony now keeps his OWN realized ledger
   (`workspace/tony-realized.json`); the old verdict-vs-scanner line is relabeled
   "Scanner-verdict accuracy". Realized record also feeds self-review.
3. **No P/L in recap:** the Telegram daily recap now shows equity day Δ ($/%), open unrealized P/L,
   and realized P/L of trades closed today (win/loss).

**Verification done:** 435 tests green; tandem sandbox `python scripts/tandem_sandbox.py --self-test`
→ PASS (prod byte-for-byte unchanged, 0 real orders, all 8 live API checks incl. `telegram: True`);
independent reviewer verdict SHIP (its one MEDIUM is the fix in `343ace4`); Brave/SerpAPI both verified
healthy (Brave is now tier-2 behind the newly-added SerpAPI key).

---

## 2. ⭐ THE #1 JOB: make the wave continuous AND cost-bounded
**Current behavior (live now):** `research_wave.maybe_stage_research_wave` stages exactly ONE
full-universe wave per upcoming open (de-dup `staged_for == open_date`). So this weekend Tony does
**one ~3h pass for Monday, then idles ~57h.** Operator wants it **continuously researching while the
market is closed** — *but bounded* ("fine with spending, don't waste a million dollars in API").

**Design to implement (small, in `runner/bridge/research_wave.py` + tests):**
- Re-stage on an interval instead of once per open: add `TONY_RESEARCH_WAVE_INTERVAL_HOURS`
  (default ~4–6h). Re-stage when the market is closed AND `elapsed_since(staged_at) >= interval`.
  The idle hook only fires when the queue is empty, so cadence ≈ `max(drain_time, interval)` — no
  pile-up. Make each wave's task IDs unique (e.g. suffix with a `YYYYMMDD-HHMM` stamp) so re-passes
  don't collide with the previous wave's files in `done/`.
- **Cost cap (do together):** the off-hours budget lane `TONY_OFFHOURS_BUDGET_USD` currently
  defaults to **uncapped (inf)** in `runner/ledger/budget.py`. Set a real per-night cap in `.env`
  (e.g. `$20–50`/closed-window) so continuous re-staging can't run away. Confirm `is_budget_exceeded(off_hours=True)`
  actually halts staging when the cap is hit.
- Update `tests/runner/test_research_wave.py` (currently asserts the once-per-open de-dup + open-date
  suffix — both change).
- Restart the runner after editing (module caching — see §4).

Net effect: Tony grinds the universe, finishes, and (after the interval) starts a fresh pass with new
overnight news — busy all weekend, with a hard dollar ceiling.

---

## 3. Other follow-ups
- **Watch the first wave's QUALITY (Mon AM).** Routing is fine (`run_task` dispatches by
  `assigned_agent`; instructions come from the task body). But the 6 new task-type bodies
  (`tony_macro_synthesis`, `tony_catalyst_scan`, `tony_idea_hunt`, `tony_book_stresstest`,
  `tony_self_review`, `tony_research_rank`) are only proven on a real run — read a few `done/` outputs
  and the resulting `workspace/research-queue.json` to confirm they produce useful, non-truncated work.
- **Monday open re-check.** Confirm `scripts/preopen_reset.py` re-validates the queue against fresh
  prices and writes execution verdicts (queue survives the 09:25 flush — separate file). Also: **CARR
  & KDP entered Saturday are still held (protected)** — Monday's open re-evaluates them.
- **Optional (skipped):** Component E — surface `research-queue.json` + realized record on the Tony
  dashboard tab (`dashboard/server.py` + `index.html`).
- **Minor:** httpx logs full request URLs including the FRED `api_key` (visible in launch err logs).
  Low risk (local logs) but worth muting (`logging.getLogger("httpx").setLevel(WARNING)` or strip query).
- **Push:** `master` is ahead of origin (this work is committed but **not pushed**). Push when ready.

---

## 4. Health-check / ops commands
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen        # runner + dashboard (PID was 10132)
Get-ChildItem workspace\tasks\todo\TONY-RW-*              # remaining wave tasks
Get-Content (Get-ChildItem workspace\logs\launch-*.out.log | Sort LastWriteTime)[-1].FullName -Tail 30
```
```bash
python -m pytest tests/runner/ -q                          # 435 green
python scripts/tandem_sandbox.py --self-test               # full isolated loop (sends 2 telegram msgs)
curl -s http://127.0.0.1:8765/api/tony/book | head -c 200
```
**Runner restart (after ANY `runner/**` edit — modules are cached):** kill the `scripts/launch.py`
process + the port-8765 child, then relaunch detached:
```powershell
Start-Process python -ArgumentList "scripts/launch.py","--interval","180" `
  -WorkingDirectory "C:\Users\alexa\Downloads\AI Operations Command Center" `
  -RedirectStandardOutput "workspace\logs\launch-<ts>.out.log" `
  -RedirectStandardError  "workspace\logs\launch-<ts>.err.log" -WindowStyle Hidden
```

## 5. Do NOT
- Don't add conviction/market-hours/research logic to the BOT — it's the flat-1% control; CC-only.
- Don't edit `runner/**` and expect it live without a runner restart.
- Don't let continuous re-staging run without the off-hours `$` cap (§2) — that's the "million dollars" risk.
- Don't reintroduce closed-market entries — the gate is the whole point of Component A.
- Don't `git add -A` for these commits (the working tree has ~700 untracked files); stage explicit paths.

## 6. Key files
- Session gate / book: `runner/ledger/market_clock.py`, `runner/ledger/alpaca_paper.py` (`sync`, `_notify_closed`).
- Orchestrator: `runner/bridge/research_wave.py` (← edit for §2). Budget: `runner/ledger/budget.py`.
- Queue + open re-check: `runner/ledger/research_queue.py`, `scripts/preopen_reset.py`.
- Realized + recap: `runner/ledger/tony_realized.py`, `runner/main.py` (`_maybe_send_daily_summary`).
- Tests: `tests/runner/test_market_clock.py`, `test_research_wave.py`, `test_research_queue.py`,
  `test_tony_realized.py`, `test_recap.py`, `test_realized_defer.py`, `test_alpaca_paper.py`.
- Spec: `docs/superpowers/specs/2026-06-06-tony-off-market-research-engine-design.md`.

**Bottom line:** the engine is live and already prepping Monday. The one thing left to make it match the
"research all weekend, autonomously, without my input" goal is **continuous interval re-staging + a hard
off-hours $ cap** (§2). Everything else is verified and committed. 🚀
