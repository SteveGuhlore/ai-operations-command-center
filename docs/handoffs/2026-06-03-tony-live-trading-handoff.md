# Next-Session Handoff — Tony Stocks LIVE & Trading

**For:** a fresh Command Center session (assume zero prior context).
**Date written:** 2026-06-03 (mid-session, market open).
**One-line status:** The bot ⇄ CC loop is **live and trading** — Tony bought **HOOD + DAL** (filled, bracketed, still held) on his own **$1M Alpaca paper account**. Afternoon bridges (through 13:00) confirmed still ingesting & holding. Everything below is committed. **Open item #1 is now ROOT-CAUSED** (record path mismatch — see §4.1); next session = implement that small fix + keep watching, not a rebuild.

---

## 0. What this system is (60-second context)
Two-layer stock loop, two separate repos under `C:\Users\alexa\Downloads\`:
- **Layer 1 — the bot** (`TradingBotAgentProject`): scans ~349-symbol universe, trades its **own** paper account `PA3P0RN75VL1`, and drops markdown **bridges** into this repo's `bridge/tony-stocks/`.
- **Layer 2 — "Tony Stocks"** (this repo, agent `market_research_worker`, gemini-2.5-pro): ingests the bridge, does an independent deep-dive (live prices, technicals, news), writes structured **verdicts**, and trades his **own $1M Alpaca paper account** (key ends `…K5ZP`). The bot reads his verdicts for the record only — **never acts on Tony's book**.
- Both books are graded against the **same outcomes** → the "does the 2nd pass make money?" experiment. **Accounts never share keys.**

Bot's own handoff (their side, authoritative for the contract): pasted in chat 2026-06-03; prior CC handoff: `docs/handoffs/2026-06-02-next-session-readiness.md`.

---

## 1. The file contract (bot ⇄ CC)
| File | Owner | Purpose |
|---|---|---|
| `bridge/tony-stocks/YYYY-MM-DD.md` | bot writes | **daily** deep-dive anchor (first scan each ET morning) |
| `bridge/tony-stocks/YYYY-MM-DDTHHMM.md` | bot writes | **intraday** light updates (10:30 / 13:00 / 15:30 ET + EOD) |
| `../TradingBotAgentProject/reports/tony_stocks_outcomes.json` | bot writes | resolved outcomes (range-join on pick_date+resolved_date) → CC grading |
| `../TradingBotAgentProject/reports/tony_stocks_verdicts.json` | **CC writes** | Tony's structured verdicts; bot reads for record only |
| `../TradingBotAgentProject/reports/tony_stocks_record.json` | **CC writes** | win_rate / agreement / calibration; bot's dashboard reads it |

The CC paths above resolve **by default** because the two repos are siblings under `Downloads` (`alpaca_paper`/`tony_scorecard` walk up 4 parents). `TONY_OUTCOMES_FILE` is also set explicitly on the runner as belt-and-suspenders.

---

## 2. LIVE STATE right now (verify these first)
- **Runner + dashboard:** launched via `python scripts/launch.py --interval 180` (detached, `-WindowStyle Hidden`, logs in `workspace/logs/launch-*.err.log`). **Find current PID:** `Get-NetTCPConnection -LocalPort 8765 -State Listen`. Dashboard: http://127.0.0.1:8765 .
- **Tony's Alpaca account:** new **$1M** paper account, key `…K5ZP`, in `.env`. (The original account had been **closed** → operator made a new one; the closed account was the reason for an earlier 0-trade red herring.)
- **Open positions today:** HOOD + DAL (filled, bracketed). Scorecard live: `record.json` = `verdicts 7, graded 6, win_rate 33.3%, override_saved 2 / override_missed 4`.
- **Pre-open reset:** Windows Scheduled Task **`TonyPreOpenReset`** runs weekdays **09:25 ET** → `scripts/preopen_reset.py` cancels orders + clears executed-log + empties verdicts so each day starts clean. (Verify: `Get-ScheduledTaskInfo TonyPreOpenReset`.)
- **Remote view:** Tailscale Serve → `https://alexandria.tail0ae2dc.ts.net` (tailnet-only) proxies :8765. PC must stay **logged in + awake** (AC sleep already = never); **locking is fine, logging off kills the runner + task.**
- **Quiet mode:** `OUTREACH_PAUSED=True`, Prospector/opportunity pipeline runway expired → only Tony runs.

⚠️ **The runner caches Python modules at launch — any `runner/**` edit needs a runner RESTART to go live** (kill the launcher + the port-8765 child, confirm port frees, relaunch). This bit us repeatedly today.

---

## 3. What got fixed today (all committed on `master`)
- `e8216d1` — intraday bridges ingest (`…THHMM.md`) as their own runs + **light** intraday task vs full daily deep-dive; bracket orders use **whole-share qty** (Alpaca rejects notional+bracket); **reaffirm inherits scanner target/stop** so no naked longs.
- `659549a` — paper executed-log keyed by **intent** (`date:symbol:open|close`) so an intraday close fires after that day's buy.
- `cabe048` — **dashboard wired to the real book**: `/api/tony/book` + "Paper Book" & "Structured Verdicts" panels (was only parsing the prose signal-ledger).
- (pre-open reset commit) — `flush_session()` + `scripts/preopen_reset.py` + the 09:25 scheduled task.
- `1b01fba` — **memory-poison fix** (the unblocker): `_load_vault_history` now filters broken-scan/no-op runs (`_HISTORY_POISON`) so their "data integrity failure / mass exit / no signals" narrative stops anchoring Tony into skipping analysis. **Paired with a manual reset of `vault/tony-stocks/signal-ledger.md`** to a clean baseline (vault is gitignored, so that reset is NOT in git — it lives in the working vault).
- `6e3213c` — **D bracket guard**: `write_tony_verdict` rejects `adjust`/`override` with `target ≤ stop`; `plan_orders` skips degenerate brackets (D had `target==stop==66.53`).
- `d75b6f2` — ROADMAP: HIGH-priority **dashboard mobile-polish** item (UI unreadable on phone).

Tests: full suite green (`python -m pytest tests/runner/ evals/ -q`).

---

## 4. OPEN ITEMS for the next session
1. **(Main — ROOT-CAUSED, ready to fix) The Scout→Forge "no-op" is a symptom of a record-path mismatch.**
   - **Root cause:** `write_record()` (in `runner/ledger/tony_scorecard.py`) writes `tony_stocks_record.json` to **`../TradingBotAgentProject/reports/`** (where it exists, with real data: `graded 6, win_rate 33.3%`). But Tony's **weekly self-review looks for it in `vault/tony-stocks/tony_stocks_record.json`** → so Tony falsely reports it "missing" → Scout files a `critical` bug → hands Forge (`heavy_worker`) a *vague* "investigate & fix" task about a non-bug (`workspace/tasks/done/AUTO-20260603-115402-fix-missing-tony-stocks-record.md`) → Forge finds no real bug and just re-escalates = the no-op. **Forge isn't broken; it was handed a non-bug.**
   - **The fix (small):** (a) mirror `write_record()` to also write `vault/tony-stocks/tony_stocks_record.json` (where Tony looks) — *safer/simpler*, OR (b) point the self-review read path at the real `reports/` path. **First verify** the exact read path (`runner/ledger/tony_self_review.py` or wherever the record is read with a `vault/` prefix). Add a test + restart the runner.
   - **Optional hardening:** make Scout-spawned Forge tasks carry concrete bug details (exact file path + generator function) so Forge has something actionable, not "go investigate."
2. **(Watch) Afternoon/again-trading:** confirm the 13:00 / 15:30 / EOD bridges keep ingesting → verdicts → fills. D will now either get a **valid** bracket (target>stop) or be passed — never a broken order.
3. **(Nice-to-have) Dashboard mobile polish** — see ROADMAP top item; UI is desktop-only, unreadable on the Tailscale phone view.
4. **(Bot-side, after 16:00 ET)** bot will add `GET /api/command-center` to read `record.json` for its head-to-head dashboard. No CC action needed beyond keeping `record.json` written (already automatic each cycle).

---

## 5. Health-check commands (paste into a fresh session)
```powershell
# runner up?
Get-NetTCPConnection -LocalPort 8765 -State Listen
# pre-open reset armed?
Get-ScheduledTaskInfo TonyPreOpenReset
```
```bash
# tests green
python -m pytest tests/runner/ evals/ -q
# Tony's live book ($1M account) + verdicts
python -c "from dotenv import load_dotenv; load_dotenv(); from runner.ledger.alpaca_paper import paper_book; print(paper_book())"
# scorecard (grading live)
python -c "from runner.ledger.tony_scorecard import compute_record; print(compute_record())"
```

## 6. Key files & envs
- Ingestion: `runner/bridge/tony_bridge.py` (`_make_brief_from_bridge` full / `_make_intraday_brief` light / `_load_vault_history` + `_HISTORY_POISON`)
- Paper book + reset: `runner/ledger/alpaca_paper.py` (`sync`, `plan_orders`, `paper_book`, `flush_session`) | CLI `scripts/preopen_reset.py`
- Verdict tool: `runner/tools/tony_verdict.py` (target>stop guard) | Learning: `runner/ledger/tony_scorecard.py`
- Cycle wiring: `runner/main.py` `run_cycle` (scan → dispatch → write_record → alpaca sync) | Dashboard: `dashboard/server.py` `/api/tony/book`, `/api/tony/stocks`
- Envs: `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` (the **$1M** account, key `…K5ZP`), `TONY_OUTCOMES_FILE`, `TONY_PAPER_NOTIONAL` ($/position, default 1000)

## 7. Do NOT
- Don't un-pause outreach/Prospector (quiet mode is intentional).
- Don't share Alpaca keys between bot and Tony (separate books is the whole experiment).
- Don't edit `runner/**` and expect it live without a **runner restart**.
- Don't re-introduce the broken-data narrative into `signal-ledger.md` — it anchors Tony into not trading.

**Bottom line:** loop is live, Tony is trading the $1M account, scorecard is grading, all guards committed. Next session = confirm afternoon trades keep flowing and resolve the Scout→Forge no-op (#1). 🚀
