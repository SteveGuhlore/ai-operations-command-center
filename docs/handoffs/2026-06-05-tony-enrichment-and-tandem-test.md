# Next-Session Handoff — Make Tony smarter + full bot⇄Tony tandem test

**For:** a fresh Command Center session (assume zero prior context).
**Written:** 2026-06-05, after a long dashboard/learning session.
**Two-part mission:** (A) **enrich `market_research_worker` (Tony) so his calls are measurably better**, then (B) **test the whole bot⇄Tony loop end-to-end with the scanner until it runs with zero hiccups.**

---

## 0. What this system is (60-second context)
Two separate repos under `C:\Users\alexa\Downloads\`:
- **The bot** (`TradingBotAgentProject`): a quantitative scanner over ~548 symbols. Trades its own **$100k** Alpaca paper account and drops markdown **bridges** into this repo's `bridge/tony-stocks/` ~5×/day (≈09:30 / 10:30 / 13:00 / 15:30 / 16:00 ET; the EOD slot is `…T1600.md`).
- **Tony / Command Center** (this repo): agent `market_research_worker` on **gemini-2.5-pro**. Ingests each bridge, does an **independent research pass** (fundamentals, technicals, news, regime), writes structured **verdicts**, and trades his own **$1M** Alpaca paper account. The experiment: *does the second reasoning pass beat the raw scanner?* Compared on **%-return**.
- **Golden rule:** pure one-way file hand-offs. If either side writes nothing, the other still runs.

Prior handoff: `docs/handoffs/2026-06-04-tony-headtohead-and-dashboard.md`. Parity contract: `../TradingBotAgentProject/docs/CONTRACTS/execution-parity.md`. The bot side also left a coordination doc: `../TradingBotAgentProject/docs/CONTRACTS/CC-sync-handoff.md` — **read it before the tandem test** (§B).

---

## 1. State at handoff (all committed on `master`)
Recent session shipped (newest first):
- `8de8e7c` Tony column on Scanner Signals — each scanner pick now shows what Tony did (held·call / held·pass⚠ / passed / —not-analyzed); renamed panels to make **bot-owned vs Tony-owned** unmistakable.
- `403ef6e` **Fix B** — per-ticker fan-out enabled (`TONY_FANOUT_MIN_TIER1=3`, `MAX=6`) + daily/intraday briefs lightened to a synthesis pass so they stop hitting the 50-step tool cap.
- `58d63e4` Tracked/Scanner Signals enriched (Score/Price/Target/Stop), reordered (Paper Book → Signals → Tony's Calls → equity), paginated 15/page, live last-trade prices.
- `d5e0583` test-isolation fix — `_signal_ledger_path()` resolves from `VAULT_DIR` at call time so running `pytest` can't corrupt the real vault (it did once).
- `9bb8df8` deterministic `signal-ledger.md` refresh from the bridge (+ monotonic guard so it never moves backward in time).
- `dd6e22a` live-price marking (`equity_history.mark_live`) on the Paper Book **and** the head-to-head curve — symmetric with the bot; `load_dotenv()` in `dashboard/server.py`.
- `a6df3d5` improvement-loop scoped to active agents + `_is_safe_rewrite` guard.
- `e80c632` equity-curve self-heal on launch.

**Live now:** runner + dashboard on :8765 (single launcher), Tony book = 11 GTC-protected positions, equity ~$1,000,142 (live-marked). **342 tests green** (`python -m pytest tests/runner/ -q`).

---

## 2. Known gaps Tony has TODAY (the "why" for Part A)
Concrete, evidence-backed — these are what to fix:
1. **Coverage was thin.** Before Fix B the daily brief truncated at ~10 of ~26 Tier-1 names (50-step tool cap). Fix B should fix this — **verify it actually does** on the next open (expect more verdicts, fan-out tasks `TONY-TKR-*`).
2. **No outcome feedback loop in the decision itself.** Tony writes verdicts but doesn't *see his own hit rate*. He can't tell that, say, his "Breakout Watch reaffirm" calls lose 60% of the time. `reports/tony_stocks_outcomes.json` exists as ground truth but Tony has no tool to read it.
3. **Pass ≠ close (the amber ⚠ case).** Tony holds CRM/FCX despite "pass" verdicts because a pass doesn't exit an existing position — only "close" does. Stale carry-over distorts the book.
4. **Flat sizing.** Every entry is 1% risk regardless of conviction — a 93-score `C` is sized like a 75-score name.
5. **Soft macro/sector/pattern overlays.** The prompt *describes* a regime/sector/pattern-library overlay, but nothing enforces it — it depends on the LLM remembering. Earnings-in-window and analyst-target-below-price are "should" rules, not guards.
6. **Calibration unknown.** Is `tony_score` predictive? Does `confidence: high` actually outperform `low`? Unmeasured.

---

## 3. PART A — Make Tony smarter (the build)

Tony's surface: model `gemini-2.5-pro`; tools `web_research, get_stock_data, get_price_history, regime, file_editor, tony_insights, tony_verdict, tony_idea, task_creator, flag_issue, memory`; `max_steps=50` (`runner/agents/base.py`); prompt `agents/market_research_worker.md`; brief bodies built in `runner/bridge/tony_bridge.py`; learning via `scripts/improvement_loop.py` (daily, runner hook) + weekly Sage (`librarian`) + per-task `auto_write_task_memory`.

**Build in this order — each is independently shippable, lowest-risk first.**

### Tier 1 — Close the feedback loop (highest leverage)
- **Outcome-aware verdicts.** Add a read-only `tony_outcomes` tool that summarizes `reports/tony_stocks_outcomes.json` into per-setup / per-verdict hit-rate, expectancy, and avg R-multiple. Inject a compact "your track record" block into Tony's brief so he conditions on what actually works. *Files:* new `runner/tools/tony_outcomes.py`, register in `main.py` ROLE_TOOLS, surface in the brief body.
- **Self-grading pass.** There's already a `tony_self_review` task type (`main.py:626`). Make it real: nightly, Tony reviews closed trades vs his verdict and writes 1–3 `write_tony_insight` lessons + updates `vault/agents/market_research_worker/learned_rules.md`. Verify it actually runs and the lessons feed the next brief.
- **Consume the bot's nightly self-learning brief.** The bot now writes a nightly learning brief to `{cc}/bridge/tony-stocks/learning/` (see CC-sync-handoff §1). Ingest it as **advisory context** in Tony's brief (dedupe by date, never let it override his independent call).

### Tier 2 — Enforce the overlays (turn "should" into guards)
- **Earnings-in-window hard guard.** If `get_stock_data` next-earnings date falls inside the expected hold window, auto-flag the verdict (and prefer pass/smaller size). Make it a structured field, not prose.
- **Analyst-target sanity.** If analyst target < current price, surface a red flag on the verdict.
- **Regime + sector overlay, deterministic.** Use the `regime` tool result + `vault/macro/sector-rotation.md` to apply a one-tier confidence downgrade in risk-off / lagging sectors — computed, not remembered.
- **Pattern library application.** `vault/tony-stocks/pattern-library.md` rules (day-4 fade, cluster risk) applied as pre-research filters.

### Tier 3 — Decision quality
- **Conviction-scaled sizing.** Within the 1% risk cap, scale notional by `tony_score` band (e.g. 90+ full, 80–90 ¾, <75 pass). Keep parity contract intact (1% risk floor, $10k cap). **Coordinate with the bot side** so the head-to-head stays apples-to-apples.
- **Exit discipline / "pass → close" rule.** Decide policy: when Tony passes on a held name N days running (or thesis breaks), should intraday issue a `close`? Removes the amber ⚠ carry-over drift.
- **Score & confidence calibration.** Add an analytics step (offline, read-only) that checks whether `tony_score` / `confidence` predict outcomes; feed the finding into the prompt.

### Tier 4 — Tooling/scale
- **Tune fan-out.** After observing the next open, set `TONY_FANOUT_MAX` to cover the conviction set without backing up the single-task-per-cycle runner (watch queue depth). Consider fan-out only on the daily + EOD bridge, not every intraday slot, if the queue floods.
- **Raise `max_steps` for the daily brief task type** only if synthesis still truncates (per-task-type cap in `base.py`).

**Method:** follow the repo's plan-first rule (`CLAUDE.md`) and use the `dispatching-parallel-agents` skill for any shared-state logic (implement + independent review). Every Tony change is gemini-pro behavior on a **live paper-trading** system — ship behind tests, restart the runner (runner caches modules — see §5), and watch one real cycle before trusting it.

---

## 4. PART B — Full bot⇄Tony tandem test (the "zero hiccups" goal)

Goal: prove the whole loop — **scanner → bridge → ingest → Tony analysis → execution → dashboard → learning** — runs clean across a real session. Do this AFTER Part A, then re-run as the acceptance gate.

### Pre-flight (both repos up)
```powershell
# CC (this repo)
Get-NetTCPConnection -LocalPort 8765 -State Listen        # runner + dashboard
Get-ScheduledTaskInfo TonyPreOpenReset                    # 09:25 ET reset armed
# Bot (other repo): trading_bot.cli watch + API on :8001
(Invoke-WebRequest http://127.0.0.1:8001/api/paper/positions -UseBasicParsing).StatusCode
```
Confirm: `.env` has `GOOGLE_AI_API_KEY` + Alpaca keys (Tony key ends `…K5ZP`); bot and Tony **never share keys**.

### Stage-by-stage acceptance (each must pass with no manual fix)
1. **Bridge ingestion.** A fresh bridge lands in `bridge/tony-stocks/`. Expect: ledger `Last updated` advances to today (green badge, not stale); a `TONY-DAILY-BRIEF-*` (or intraday) task created; `TONY-TKR-*` fan-out tasks created; **no duplicate** tasks on re-scan; no older bridge reverts the ledger (monotonic guard). *Check:* `workspace/logs/tony-bridge-processed.json`, `workspace/tasks/todo/`.
2. **Tony analysis.** Tony runs without truncating; produces verdicts for the fanned-out names **plus** synthesis insights; **no hallucinated `<invoke>` tool calls** (the old gemini bug — must be real tool calls); verdicts land in `tony_stocks_verdicts.json`. *Check:* the session file in `vault/sessions/<date>/`, verdict count vs Tier-1 count.
3. **Execution.** Entries placed with **GTC bracket** (target+stop OCO); sizing = 1% risk / $10k notional cap; **no pyramiding** a held name; the OCO reconciler re-attaches protection to any naked position. *Check:* `/api/tony/book` orders, `runner/ledger/alpaca_paper.py` logs.
4. **Dashboard.** Paper Book shows **live** prices + `priced_live: true`; Scanner Signals shows Score/Price/Target/Stop + correct **Tony** badges; equity curve draws **both** lines; pagination works; mobile (Tailscale URL) is legible.
5. **Head-to-head parity.** Bot and Tony use the same risk rules (1% risk, 50 positions, 200 daily orders); both books marked to **live** prices (no stale-mark asymmetry). Bot ≈ its reference %; Tony's % reflects live marks.
6. **Overnight + reset.** GTC legs survive the 16:00 close; `TonyPreOpenReset` at 09:25 ET cancels only **unfilled entries**, keeps protective legs, clears verdicts/executed-log, queues the pre-open deep-dive.
7. **Learning (no prod corruption).** Nightly `improvement_loop` (after 2 AM, runner hook) + weekly Sage run; `_is_safe_rewrite` blocks any unsafe prompt rewrite; **running `pytest` does NOT mutate the real vault** (regression-guard the `d5e0583` fix).

### Hiccup hunt (the part that's easy to skip)
- Run `python -m pytest tests/runner/ evals/ -q` → **green**, and confirm the production ledger/tasks are **unchanged** afterward.
- Force a restart mid-session and confirm: single launcher (no duplicate-runner pileup), ledger holds (no revert), orphaned `in_progress` tasks re-queued, locks cleared.
- Drop an **old** and a **malformed** bridge: old must be rejected by the monotonic guard; malformed must no-op (never wipe the ledger).
- Kill the bot API (:8001) and confirm the CC dashboard degrades gracefully ("awaiting Command Center" / live-price fallback), never 500s.

### Cross-repo coordination (do first — from the bot's CC-sync-handoff)
The bot expects CC to: point its 2 AM script at `{cc}/bridge/tony-stocks/learning/`; keep `TONY_OUTCOMES_FILE` → bot's `reports/tony_stocks_outcomes.json`; keep writing `tony_stocks_verdicts.json` + `tony_stocks_record.json` (incl. `equity_curve`); keep Tony's curve/book **live-marked**; dedupe the intraday + `…T1600.md` EOD bridges (EOD was relabeled `eod`→`1600` to avoid a filename collision); verify risk/caps match `execution-parity.md`.

---

## 5. Health-check commands
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen
Get-ScheduledTaskInfo TonyPreOpenReset
```
```bash
python -m pytest tests/runner/ -q                                   # 342+ green
curl -s http://127.0.0.1:8765/api/tony/stocks | head -c 400         # ledger fresh + tony_state
curl -s http://127.0.0.1:8765/api/tony/book   | head -c 400         # priced_live true, equity
curl -s http://127.0.0.1:8765/api/tony/equity-curve | head -c 300
```

## 6. Do NOT
- Don't edit `runner/**` and expect it live without a **runner restart** (detached `launch.py` caches modules: kill launcher + the port-8765 uvicorn child, relaunch `python scripts/launch.py --interval 180`).
- Don't let any change make the bot and Tony share Alpaca keys, or change one book's risk params without the other (parity).
- Don't reintroduce a hand-written `signal-ledger.md` path constant — keep `_signal_ledger_path()` (tests corrupt prod otherwise).
- Don't let an automated prompt rewrite drop Tony's guardrails — `_is_safe_rewrite` must stay.
- Don't revert Tony to flat `$1000` sizing or stale Alpaca marks.

## 7. Key files
- Tony brain: `agents/market_research_worker.md` · model/tools `runner/main.py` (MODELS, ROLE_TOOLS) · loop cap `runner/agents/base.py:144`.
- Bridge → tasks + ledger: `runner/bridge/tony_bridge.py` (`_make_brief_from_bridge`, `_make_intraday_brief`, `_refresh_signal_ledger`, fan-out).
- Execution/sizing/protection: `runner/ledger/alpaca_paper.py`.
- Live marking + curve: `runner/ledger/equity_history.py` (`mark_live`, `snapshot`, `backfill`).
- Verdict tool: `runner/tools/tony_verdict.py`. Outcomes ground truth: `reports/tony_stocks_outcomes.json`.
- Learning: `scripts/improvement_loop.py` (+ Sage via `runner/main.py` `_maybe_run_learning`).
- Dashboard: `dashboard/server.py` (`/api/tony/stocks` join, `/api/tony/book`) + `dashboard/index.html` (Tony tab).
- Contracts: `docs/CONTRACTS/` here and in the bot repo (esp. `execution-parity.md`, `CC-sync-handoff.md`).

**Bottom line:** Part A makes Tony learn from his own results and stop leaking edge (coverage, calibration, overlays, exits). Part B proves the bot⇄Tony machine runs end-to-end with zero manual rescue. Do A behind tests + a watched cycle, then run B as the gate. 🚀
