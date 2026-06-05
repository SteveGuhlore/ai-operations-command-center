# Next-Session Handoff — verify the close/notify fixes at the open

**Written:** 2026-06-05 EOD (after live day 1 of full operation).
**For:** a fresh Command Center session, picking up at the **next market open**.
**Decision locked this session:** **Option A** — we did NOT force-close the positions Tony decided to
exit today (C, CVS, DXCM, CSX). They stay open overnight (protected), and the **now-fixed system
re-evaluates + closes them at the open**. The #1 job next session is to **confirm that actually happens**.

---

## 0. 60-second context
Two sibling repos under `C:\Users\alexa\Downloads\`: the **bot** (`TradingBotAgentProject`, layer-1
quant scanner, $100k Alpaca paper) drops markdown **bridges** into this repo's
`bridge/tony-stocks/` ~5×/day; **Tony / Command Center** (this repo, `market_research_worker` on
gemini-2.5-pro, $1M Alpaca paper) ingests each, does an independent 2nd-pass, writes verdicts, and
trades. Golden rule: one-way file hand-offs. Live alerts go to a **Telegram supergroup**
(`TELEGRAM_CHAT_ID=-1004291554939` in `.env`, gitignored).

**Day 1 result (2026-06-05):** full loop ran clean — 5 handoffs ingested, 17 verdicts (all 5 types),
execution + reprices, and **Tony beat the bot −0.09% vs −1.16%**. Then a live review found 4 bugs,
all fixed below.

---

## 1. State at handoff (all committed on `master`)
Newest first:
- `459e85c` **the 4 live-review fixes** (see §2) — close flattens, protection every cycle, alerts fixed.
- `1edbefb` idle-time learning now fires on an empty queue (was skipped overnight).
- `4595bc9` / `1e2c193` / `4c6cac6` tandem sandbox harness (`scripts/tandem_sandbox.py`) — isolated,
  self-cleaning, covers ingest→verdict→execution(mock)→all APIs→teardown.
- `d77dd4f` Telegram trade alerts (entry/exit/daily, now + reprice).
- `7110537` `record.json` + verdict schema aligned to the bot's reader contract.
- `16e6dcd` `tony_outcomes` feedback loop + 4 data APIs (Alpaca news, SEC EDGAR catalysts, Finnhub
  analyst/earnings, FRED rates).

**Live now:** runner + dashboard on :8765 (restarted with the fixes), Tony book ~$999k / 12 positions,
**375+ tests green**. The bot side independently ran `scripts/tandem_loop_test.py` → **25/25 green,
zero corruption**.

---

## 2. The 4 fixes shipped today (what to trust, what to verify)
From the live day-1 review (commit `459e85c`):
1. **Entry alert risk label** — was "100% risk", now **"1% risk"** (`RISK_PCT=1.0` means 1%; stopped ×100). Cosmetic; sizing was always correct.
2. **`close()` now actually flattens** — a held position's GTC stop/target SELL legs HOLD the shares,
   so a bare `close_position` silently no-opped and the position stayed open. `close()` now **cancels
   the protective legs first, then retries** the liquidation. *(`runner/ledger/alpaca_paper.py` `_Broker.close`)*
3. **Sync runs every cycle, not just on bridges** — the empty-queue early-return skipped `alpaca_sync`,
   so stop-outs went unannounced ~1h and older positions lost protection between bridges. Now
   `alpaca_sync` + `write_record` run on idle cycles too. *(`runner/main.py` `run_cycle` idle branch)*
4. **Reprice (`adjust`) is now notified** — `🔧 Tony re-priced …`. *(`notify_reprice`)*

These are unit-covered (38 affected tests green) but **#2 and #3 are only fully proven live at a real
open** — that's §3.

---

## 3. ⭐ THE #1 JOB: verify the close fix at the open
Tony issued `close` on **C, CVS, DXCM, CSX** yesterday; they did NOT flatten (the bug) and are still
held. They're marked done for 2026-06-05, so they won't auto-retry overnight. At the open:

1. **09:25 ET** `TonyPreOpenReset` clears yesterday's verdicts/executed-log + queues the pre-open deep-dive.
2. First bridge → Tony re-evaluates C/CVS/DXCM/CSX with **fresh overnight data**.
3. If he still says `close`, the **fixed `close()` should now flatten them** — and you should get a
   🔴 exit alert in Telegram.

**Verify:**
- Watch the Telegram group for entry/exit/reprice alerts firing **promptly** (within a cycle, not ~1h late).
- `curl http://127.0.0.1:8765/api/tony/book` → confirm names Tony closes actually leave the book.
- Grep the runner log for `close cancel` + a successful liquidation (no "gave up after retries").
- Confirm **older positions stay protected** between bridges (every-cycle reconcile) — no naked positions.

If a close still fails to flatten, check `_Broker.close` retry path + whether the symbol's sell legs
were actually canceled (Alpaca async qty release can need the retry loop).

---

## 4. Open items / follow-ups (not blocking)
- **Bot-side close fix:** the same cancel→close→retry pattern should be applied to the bot's flatten
  path (esp. its `cc_exit_symbols` flatten-on-CC-`close`). Prompt already given to the scanner session.
- **Tony two-way Telegram Q&A** (user wants it): a listener that reads incoming messages and lets Tony
  answer "why <TICKER>?" from his stored thesis (instant tier) + full gemini Q&A grounded in his book.
  ~half a day; start with the instant-`why` tier. CC-internal, touches nothing in the bot⇄CC contract.
- **Record `graded` is still ~1** — only one of Tony's picks has a resolved outcome; win-rate is noise
  until more positions close. It fills in over coming days.
- **Force-close option (declined today):** if you ever want to honor a same-day exit regardless of the
  next open's re-evaluation, we can queue a market close for specific names — explicit go required.
- **Fractional positions** (e.g. SLB 0.59 sh) can't carry a whole-share bracket → effectively
  unprotected. Minor; worth a guard later.

---

## 5. Health-check commands
```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen        # runner + dashboard
Get-ScheduledTaskInfo TonyPreOpenReset                    # 09:25 ET reset armed
```
```bash
python -m pytest tests/runner/ -q                                   # 375+ green
curl -s http://127.0.0.1:8765/api/tony/book   | head -c 200        # equity, positions
curl -s http://127.0.0.1:8765/api/tony/equity-curve | head -c 200  # Tony vs bot %
python scripts/tandem_sandbox.py --self-test                        # full isolated loop (sends 2 telegram msgs)
```
**Runner restart (after any `runner/**` edit — modules are cached):** kill the `scripts/launch.py`
process + the port-8765 child, relaunch `python scripts/launch.py --interval 180` (redirect stdout/err
to `workspace/logs/launch-<ts>.*.log` for visibility).

---

## 6. Do NOT
- Don't force-close the 4 names tonight — Option A is locked (let the open re-decide).
- Don't edit `runner/**` and expect it live without a runner restart.
- Don't let the bot and Tony share Alpaca keys, or change one book's risk params without the other (parity: 1% risk, CC $10k / bot $1k cap, 50 open, 200 daily).
- Don't reintroduce the empty-queue early-return that skips `alpaca_sync`/learning.

---

## 7. Key files
- Close/sizing/protection: `runner/ledger/alpaca_paper.py` (`_Broker.close`, `_reconcile_protection`, `_reprice_adjusted`, `risk_based_qty`).
- Cycle orchestration: `runner/main.py` `run_cycle` (idle branch now runs sync+learning).
- Alerts: `runner/tools/notify.py` (`notify_entry/exit/reprice/daily`); hooks in `alpaca_paper.sync`.
- Record/grading: `runner/ledger/tony_scorecard.py` (full bot-contract schema).
- Tandem test: `scripts/tandem_sandbox.py` (CC half) + bot's `scripts/tandem_loop_test.py`.
- Contracts: `../TradingBotAgentProject/docs/CONTRACTS/` + `docs/TEST-PLANS/2026-06-05-full-e2e-sync-test-CC-side.md`.

**Bottom line:** everything's fixed, committed, tested, and live. The next session's real job is small
and specific — **watch the open and confirm Tony's `close` now flattens (and alerts fire on time)**.
If it does, this bug is closed for good. 🚀
