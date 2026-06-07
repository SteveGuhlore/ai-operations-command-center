# Next-Session Handoff — Telegram companion + realized-ledger fix LIVE; Telegram Tiers 1–4 next

**Written:** 2026-06-06 (Sat) eve ET. **For:** a fresh Command Center session.
**State:** everything below is committed AND pushed to `origin/master` (tip `0773991`), **runner
restarted and live on :8765 (pid 4236)**, all **464 tests green**.

---

## 0. 60-second context
Two layers only: **the bot** (`TradingBotAgentProject`, quant scanner, $100k Alpaca paper, drops
markdown bridges into `bridge/tony-stocks/`) and **Tony** (this repo, `market_research_worker` on
gemini-2.5-pro, $1M Alpaca paper, independent 2nd pass). ONE agent does everything Tony does — no new
runtime personas; research "tasks" are TASK TYPES. Golden rule: one-way file hand-offs. Alerts →
Telegram. Runner = detached `scripts/launch.py` → child on :8765; **edits under `runner/**` need a
runner restart** (module caching — see §5). Don't `git add -A` (working tree has ~700 untracked files);
stage explicit paths.

---

## 1. What shipped THIS session (master, newest first)
- `0773991` docs: **Telegram "face of the agent" roadmap** (Tiers 1–4) —
  `docs/superpowers/specs/2026-06-06-tony-telegram-face-roadmap.md`.
- `0c08c32` **fix: realized ledger reconciled from Alpaca fills** (the big correctness fix — see §2).
- `5c4fec7` **feat: Telegram Phase 3** — first-person LLM synthesis (daily wrap, weekly review,
  learning digest) via `runner/tools/tony_synthesis.py`.
- `df3edf6`-ish range / Phase 2 commit — **two-way chat** `runner/tools/telegram_inbox.py`
  (`/status /record /explain /glossary /help`, whitelisted to `TELEGRAM_CHAT_ID`, read-only).
- Phase 1 commit — **first-person "Tony voice"** `runner/tools/tony_voice.py`; `notify_*` now wrap it;
  entry alert carries the verdict thesis, exit restores reason (target/stop/close) + R-multiple.
- `df3edf6` **fix(logging):** mute httpx INFO so FRED/Finnhub/SerpAPI `api_key` stops leaking to logs.
- `175951b` **feat: off-hours self-learning research ROUNDS** (earlier in the session) —
  `research_wave.maybe_stage_research_followups()` stages deeper rounds after the main wave drains.
  Spec: `docs/superpowers/specs/2026-06-06-tony-offhours-self-learning-rounds-design.md`.

Specs added: telegram-companion-design, telegram-face-roadmap, offhours-self-learning-rounds.

---

## 2. ⭐ The realized-ledger fix (most important — read before touching ledger code)
**Problem the operator caught:** `/record` said "0% of 1 graded call" but there were multiple stop-outs
on Friday. Root cause: `tony-realized.json` was built ONLY by live cycle-to-cycle diffing
(`alpaca_paper._notify_closed` comparing this cycle's positions to last cycle's snapshot). Exits that
closed while the runner wasn't watching (restart, the "first-cycle no false exits" rule, telegram off)
were never recorded — and the ledger held one **bogus `HELD / unknown / $0` row**.

**Fix (live):** `alpaca_paper.reconcile_realized()` rebuilds the ledger from Alpaca's authoritative
filled-order history, FIFO-matching each SELL to prior BUYs to compute real P/L
(`tony_realized.reconcile_from_fills` / `rebuild_from_fills`). Dedups by **exit order id**, drops
legacy un-id'd rows (kills the bogus one), and **never invents an entry** (a SELL with no matching BUY
in the window is skipped). `broker.filled_orders()` is the read-only fetch. Wired into BOTH cycle
branches (idle + post-batch). `_notify_closed` still fires the exit ALERT but **no longer writes the
ledger**. `/record` + the daily recap now LEAD with the real closed-trade record
(`tony_voice.say_record(rec, edges, realized)`); scanner-verdict accuracy is a secondary line.

**Verified:** live backfill recovered Friday's 4 real stops — **FCX −$60.20, FCX −$462.20, SLB
−$39.95, SNAP −$383.18 = −$945.53**, all reason=stop. `/record` now reads:
"I've closed 4 trades — 0 winners, 4 losers — and lost $946. 4 of those were me cutting a loss at my
stop — discipline, not failure."

**Note:** `/status` was ALREADY correct — it reads Alpaca live (`get_all_positions`). The current real
book is 12 positions (ANET, C, CRM, CSX, CVS, DAL, DKNG, DXCM, HAL, HOOD, PINS, SLB). The scanner-
verdict track (`tony_scorecard.compute_record`) is still thin ("0% of 1") because it needs the BOT to
emit outcomes — that's a different, data-gated track, not a bug.

---

## 3. Telegram companion — what's live + how it's wired
**Voice:** first person ("I", Tony is his own person), plain-English + the real numbers + a light
teach-as-you-go tone (operator wants the reader to slowly learn the what & why). Pure formatters in
`runner/tools/tony_voice.py` (`say_entry/exit/reprice/daily_header/status/record/explain`, `HELP`,
`GLOSSARY`) — unit-tested.

- **Phase 1 alerts (live, no flag):** ride existing `TONY_NOTIFY=telegram`. Entry shows the thesis
  (`alpaca_paper._verdict_thesis`), exit shows reason + R (`_r_multiple`).
- **Phase 2 chat (live, `TONY_TELEGRAM_CHAT=on`):** `telegram_inbox.poll_and_handle()` long-polls
  getUpdates with a persisted offset (`workspace/telegram-inbox-state.json`), **whitelisted to
  `TELEGRAM_CHAT_ID`** (ignores strangers, still advances offset). Routes `/status /record /explain
  /glossary /help`. Wired at the TOP of `run_cycle` (before the budget gate). READ-ONLY — never trades.
- **Phase 3 synthesis (live, `TONY_SYNTH=on`):** `tony_synthesis.py` narrates via the existing
  `AgentBase` client through one `_narrate` seam (gemini-2.5-flash). `daily_wrap` rides the daily
  digest; `weekly_review` + `learning_digest` fire once per ISO week (`workspace/notify-weekly-state.json`).
  Facts are pinned ("use only these, do not invent") to block hallucinated numbers; degrades to the
  metric digest on any failure.

**Flags added to `.env` (gitignored):** `TONY_TELEGRAM_CHAT=on`, `TONY_SYNTH=on`. Everything is
CC-internal, fail-soft, and touches NOTHING in the bot↔Tony contract.

Specs: `docs/superpowers/specs/2026-06-06-tony-telegram-companion-design.md`.

---

## 4. ⭐ THE #1 JOB NEXT: Telegram Tiers 1–4 ("face of the agent")
Operator wants ALL tiers built. Roadmap (durable plan):
`docs/superpowers/specs/2026-06-06-tony-telegram-face-roadmap.md`. Build in focused sessions, each
behind tests + a runner restart, in this order:
- **Tier 1 (start here — highest impact, now sits on honest data):** (a) **natural-language chat** —
  non-command text → an LLM reply AS Tony using live data + his tools; route in
  `telegram_inbox.reply_for` fallback to a new `tony_synthesis.answer(question, ctx)`. (b) **inline
  keyboard buttons** (Telegram `reply_markup` + handle `callback_query` in the poller). (c) **proactive
  nudges** — Tony texts first (market-open plan, stop-out heads-up, new equity high, EOD sign-off).
- **Tier 2:** `/today` `/watchlist` (from `research-queue.json`) `/research` `/learn` (via
  `tony_outcomes.lessons_block`) `/thesis SYM`.
- **Tier 3:** charts as PNGs (matplotlib → Telegram `sendPhoto`): equity curve, position-P/L bars,
  win-rate trend; attach to digests. New `tony_charts.py`; reuse `runner/ledger/equity_history`.
- **Tier 4:** lesson-of-the-day, inline glossary expansions, `/beginner` mode, persona consistency,
  milestone celebrations.
Cross-cutting: long-message chunking, `callback_query`+`sendPhoto` support in the poller, per-feature
opt-in flags, all fail-soft + READ-ONLY (chat must NEVER place/modify a trade — explicit non-goal).

---

## 5. Other follow-ups / open items
- **Off-hours self-learning rounds (175951b):** watch the FIRST real drain (Mon AM) — confirm
  `tony_calibration_study` / `tony_edge_mining` / `tony_realized_postmortem` write concrete,
  evidence-tagged lessons into `learned_rules.md` / `pattern-library.md`, not fluff. The self-learning
  loop IS closed: `prompts.py` injects `learned_rules.md`; `tony_bridge.py` injects `lessons_block()`
  into the briefs — so these lessons feed future verdicts (results-affecting), but data-gated.
- **Monday open re-check:** `scripts/preopen_reset.py` re-validates `research-queue.json` vs fresh
  prices before executing. The current 12 held positions get re-evaluated.
- **Component E (skipped):** surface `research-queue.json` + realized record on the Tony dashboard tab.
- **B1 conviction sizing:** built but INERT (shadow-measured) — separate decision to flip live.

## 6. Health-check / ops
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen        # runner + dashboard (pid was 4236)
Get-Content (Get-ChildItem workspace\logs\launch-*.out.log | Sort LastWriteTime)[-1].FullName -Tail 30
```
```bash
python -m pytest tests/runner/ -q                          # 464 green
# render Tony's chat replies / alerts (UTF-8 needed on Windows console):
PYTHONIOENCODING=utf-8 python -X utf8 -c "from runner.tools import telegram_inbox as t; print(t._record_reply())"
```
**Runner restart (after ANY `runner/**` edit):** kill the `scripts/launch.py` tree + the :8765 child,
then relaunch detached:
```powershell
$root="C:\Users\alexa\Downloads\AI Operations Command Center"
$ts=Get-Date -Format "yyyyMMdd-HHmmss"
Start-Process python -ArgumentList "scripts/launch.py","--interval","180" -WorkingDirectory $root `
  -RedirectStandardOutput "$root\workspace\logs\launch-$ts.out.log" `
  -RedirectStandardError  "$root\workspace\logs\launch-$ts.err.log" -WindowStyle Hidden
```

## 7. Do NOT
- Don't let Telegram chat place/cancel/modify a trade — it is READ-ONLY by design (safety).
- Don't reintroduce the live-diff realized write in `_notify_closed` — Alpaca reconciliation is
  authoritative now; the live write produced the bogus `HELD` record.
- Don't edit `runner/**` and expect it live without a runner restart (module caching).
- Don't add conviction/research/market-hours logic to the BOT — it's the flat-1% control; CC-only.
- Don't `git add -A`; stage explicit paths.

## 8. Key files
- Voice: `runner/tools/tony_voice.py`. Inbound chat: `runner/tools/telegram_inbox.py`. Synthesis:
  `runner/tools/tony_synthesis.py`. Outbound: `runner/tools/notify.py`.
- Realized ledger: `runner/ledger/tony_realized.py` (`reconcile_from_fills`, `rebuild_from_fills`);
  `runner/ledger/alpaca_paper.py` (`reconcile_realized`, `broker.filled_orders`, `_verdict_thesis`,
  `_r_multiple`, `_notify_closed`, `sync`). Cycle wiring: `runner/main.py` (`run_cycle`,
  `_maybe_handle_telegram_chat`, `_maybe_send_daily_summary`, `_maybe_send_weekly_synthesis`,
  `_maybe_stage_research_followups`).
- Research rounds: `runner/bridge/research_wave.py`. Self-learning surfacing:
  `runner/tools/tony_outcomes.py` (`lessons_block`), `runner/ledger/tony_scorecard.py`.
- Tests: `tests/runner/test_tony_voice.py`, `test_telegram_inbox.py`, `test_tony_synthesis.py`,
  `test_realized_reconcile.py`, `test_notify.py`, `test_alpaca_paper.py`, `test_realized_defer.py`,
  `test_research_wave.py`.

**Bottom line:** the honest-data foundation is fixed and live (Friday's stops recovered, `/record`
true), and the Telegram companion talks in Tony's first-person voice with two-way chat + synthesis.
The remaining job is **Telegram Tiers 1–4** — start with Tier 1 natural-language chat (roadmap §Tier 1).
Text the bot `/record` to see the corrected record. 🚀
