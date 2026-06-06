# Spec — Tony Off-Market Research Engine + execution/recap correctness fixes

**Status:** APPROVED 2026-06-06. **Owner:** Command Center (CC) side, Tony Stocks.
**Scope:** CC-internal only. **No bot changes; the execution-parity contract is untouched.**

---

## 0. Context (60 seconds)
Two layers, and only two, forever:
- **Layer 1 — the trading bot** (`TradingBotAgentProject`): quant scanner over ~1000 symbols,
  $100k Alpaca paper, drops markdown bridges into `bridge/tony-stocks/` ~5×/day.
- **Layer 2 — Tony Stocks** (this repo): agent `market_research_worker` on gemini-2.5-pro,
  $1M Alpaca paper. Independent second-pass research + verdicts + trades.

**Architectural invariant:** every runtime research/trading action is done by the **Tony Stocks
agent (`market_research_worker`) and only by it.** This feature adds **no new runtime agent
personas** — the four research "focuses" below are **task *types*, all assigned to
`market_research_worker`**, exactly like today's `TONY-TKR-*` fan-out. (Support agents may be
spawned *during development* to write/review/test code — never at runtime.)

---

## 1. Problem & intent
Three live defects + one new capability, discovered 2026-06-06 (a Saturday):

1. **Tony entered CARR & KDP while the market was closed.** There is no market-hours guard in
   the execution path; `alpaca_paper.sync()` → `broker.buy()` submits a GTC bracket regardless of
   session. Entries opened over a weekend gap on stale closed-market prices — anything can happen
   before the next open.
2. **The daily recap reads "1 graded" though several positions were stopped out.**
   `tony_scorecard.compute_record()` grades Tony's **verdicts against the *bot's* scanner
   outcomes** (`tony_stocks_outcomes.json`); `graded` counts only bot outcomes that match a Tony
   verdict. **Tony's own Alpaca stop-outs are never counted.** The metric is real but mislabeled,
   and Tony's actual realized record is not tracked at all.
3. **The daily recap has no P/L.** It shows equity, open-position count, and the (mislabeled)
   graded win-rate — no unrealized or realized P/L.
4. **New capability — off-market research.** On closed-market time (weeknights ~16:00→09:30 ET,
   all weekend, holidays) Tony should research and prepare for the *next* open instead of sitting
   idle: deepen the book, hunt new ideas, stress-test held positions, and learn from his own
   record — producing a ranked candidate queue that each open re-validates before executing.

**Intent:** make execution honest about market hours, make the recap reflect Tony's *real*
results, and put the idle off-hours to work — all within the two-layer, single-agent model.

---

## 2. Locked decisions (from brainstorming)
- **Research focus:** all four — prep the book, hunt new ideas, self-improvement, stress-test.
- **Handoff:** a **ranked candidate queue, re-validated at *every* market open (Mon–Fri)**.
- **Orchestration:** single agent (Tony). Structured **task-type wave on the existing runner**;
  no swarm of runtime agent personas (Approach 1, structured).
- **Breadth:** the **full scanner universe** (Tier 1+2+3) per window + synthesis/stress/self-review.
- **Window:** driven by `market_session()` = whenever the market is **closed** (handles weeknights,
  weekends, and holidays automatically; closely matches the operator's 4:30pm–9am intent).
- **Budget:** off-hours research runs in its **own high/uncapped budget lane**, separate from the
  daytime cap ("token-maxx" the research effort).

---

## 3. Components

### A. Market-session awareness (foundation)
New `market_session()` — authoritative via Alpaca `get_clock().is_open`; **fail-safe** to an
Eastern-time weekday/RTH check (`zoneinfo("America/New_York")`, Mon–Fri 09:30–16:00, best-effort
known-holiday set) when the API call fails. Result cached briefly (≤60s) to avoid hammering the
clock endpoint each cycle. Returns `"open"` or `"closed"`.

**Two consumers:**
- **Execution gate (bug #1).** In `alpaca_paper.sync()`, when the session is **closed**, skip
  `buy` actions: do **not** submit, do **not** add the key to `done`, do **not** fire an entry
  alert. `close` / `reprice` / `protect` continue to run (they only reduce risk, and the GTC OCO
  legs must keep reconciling). Entries therefore execute only at a real open, on fresh data.
- **Mode switch.** "closed" → research mode (Component B); "open" → normal execution mode.

**Files:** `runner/ledger/market_clock.py` (new, pure + a thin Alpaca call) or co-located in
`alpaca_paper.py`; gate in `alpaca_paper.sync()`.

### B. Off-market research orchestrator
A hook (in `runner/main.py::run_cycle` idle branch and/or `runner/scheduler/daily_jobs.py`) that,
when `market_session()=="closed"` **and** no wave is yet staged for the upcoming open, enqueues
one structured wave. Every task is `assigned_agent: market_research_worker`,
`pod: stock_research_pod`, mirroring the existing fan-out task format.

Wave contents (task types):
1. **`ticker_deepdive`** across the **full scanner universe** (Tier 1+2+3) — reuse existing
   deep-dive machinery (`runner/bridge/tony_bridge.py` fan-out helpers). Covers *prep* and the
   research half of *stress-test* for held names.
2. **`tony_macro_synthesis`** — regime (`regime` tool) + `vault/macro/sector-rotation.md` read.
3. **`tony_catalyst_scan`** — earnings calendar + news/SEC catalysts (`get_catalysts`,
   `get_stock_news`) across the universe + watchlist.
4. **`tony_idea_hunt`** — surface names **beyond** the scanner; writes via the existing
   `tony_ideas` tool (*hunt new ideas*).
5. **`tony_book_stresstest`** — re-examine **every open position** against fresh news; flag broken
   theses → propose `close`/`adjust` into the queue.
6. **`tony_self_review`** — the existing self-review (`main.py` self-review task), now fed by
   Tony's **real realized record** (Component D); writes `write_tony_insight` lessons + updates
   `vault/agents/market_research_worker/learned_rules.md` and `vault/tony-stocks/pattern-library.md`.
7. **`tony_research_rank`** (final, depends on the wave) — synthesize the window's verdicts + ideas
   into a scored, ranked `workspace/research-queue.json`.

**De-dup:** a per-window processed-log (e.g. `workspace/research-wave-state.json` keyed by the
target open date) so re-entering the closed window never double-enqueues. Pattern mirrors
`workspace/logs/tony-bridge-processed.json`.

**Budget lane:** off-hours wave tasks bypass / use a separate, high cap so `is_budget_exceeded()`
does not abort the wave. The **daytime cap is unchanged**.

**Throughput:** ~80–100 deep-dives @ ~1–2 min ≈ 2–3 h sequential — comfortable in a ~16.5 h night
and re-runnable many times across a ~60 h weekend. Off-hours `MAX_CONCURRENT` MAY be raised to
finish the universe faster; default unchanged if risk is unclear.

### C. Ranked candidate queue + open re-check gate
`workspace/research-queue.json` — ranked entry candidates:
`[{symbol, thesis_ref, score, confidence, proposed_target, proposed_stop, source, generated_at}]`,
sorted best-first, with a `generated_at` + target-open date header.

**Open re-check gate.** At each market **open** (the first open cycle after a closed period;
coordinate with `TonyPreOpenReset`), Tony re-validates the **top-N** queue candidates against
**fresh live prices** (`get_stock_data`), discards any whose setup/levels no longer hold, then
writes normal execution verdicts → the existing `sync()` executes them within the existing risk
caps. **Stale closed-market prices never execute directly.** The queue is a **separate file** from
verdicts/executed-log, so the 09:25 `TonyPreOpenReset` wipe does not erase it; the re-check
consumes it, then the normal verdict→sync flow proceeds.

### D. Realized-trade ledger + P/L recap (bugs #2 & #3)
Persist each closed position when `alpaca_paper._notify_closed` detects an exit, to
`workspace/tony-realized.json`:
`[{symbol, qty, entry, exit, realized_pl, pct, reason("target"|"stop"|"close"|"unknown"), date}]`.
The exit reason is inferred from the prior protective levels / fill price (best-effort).

New `tony_realized` summary (today + all-time): realized P/L, win/loss counts, by-exit-reason.

**Daily recap (`main.py::_maybe_send_daily_summary`) becomes:**
- `Equity: $X  (▲/▼ $Δ / Δ% on the day)` — from `account()` equity vs last_equity.
- `Open: N positions · unrealized P/L $Y` — sum of per-position `unrealized_pl` from `account()`.
- `Closed today: n  (w win / l loss) · realized P/L $Z` — from the realized ledger.
- `Scanner-verdict accuracy: wr% (n)` — the existing metric, **relabeled** so it is never read as
  Tony's own trade record.

The realized ledger **also feeds self-review/calibration** (B6) — Tony learns from his real
stop-outs, the true fix for "graded says 1 but many stopped out."

### E. Dashboard (optional, follow-up)
Surface `research-queue.json` and the realized record on the Tony tab (`dashboard/server.py` +
`dashboard/index.html`). Not required for acceptance; track as a fast-follow.

---

## 4. Data contracts (new files, all CC-internal, additive)
- `workspace/research-queue.json` — ranked candidates (Component C).
- `workspace/tony-realized.json` — realized-trade ledger (Component D).
- `workspace/research-wave-state.json` — per-open-date wave de-dup (Component B).

None are read by the bot; nothing in the bot⇄CC contract changes.

---

## 5. Testing (TDD; `tests/runner/`)
- **Session gate:** closed → `buy` skipped (not submitted, key not in `done`, no entry alert);
  open → `buy` executes as today; Alpaca-clock failure → ET fail-safe path; cache behavior.
- **Wave orchestrator:** closed window enqueues exactly one wave; re-entry de-dups; correct task
  types + `assigned_agent`; ET window detection across weeknight/weekend/holiday; daytime → no wave.
- **Budget lane:** off-hours wave runs past the daytime cap; daytime cap still enforced in RTH.
- **Queue + re-check:** ranker output schema; open re-check validates against fresh prices and
  **never** executes on stale queue prices; queue survives `TonyPreOpenReset`.
- **Realized ledger:** accumulates on close; reason inference; today/all-time aggregation.
- **Recap formatting:** equity Δ, unrealized, realized today, relabeled accuracy line.
- **Regression (critical):** with the market **open**, execution + recap are **byte-for-byte**
  today's behavior; daytime budget cap intact; running `pytest` does **not** mutate the real vault
  or production ledgers.

---

## 6. Risks & guardrails
- **Throughput:** bounded by the single runner; mitigated — the universe fits the window with room
  to re-run. Raise off-hours concurrency only if queue depth backs up.
- **Module caching:** runner caches modules — **restart the runner after edits** (kill
  `scripts/launch.py` + the port-8765 child, relaunch). Known gotcha.
- **Parity:** CC-internal only; **no bot changes, parity contract frozen.**
- **No new runtime agents:** the four focuses are task types under `market_research_worker`.
- **Stale-price safety:** every entry passes the open re-check gate; closed-market entries blocked.
- **Build discipline:** shared-state logic (session gate, orchestrator, queue) built with
  `dispatching-parallel-agents` (implement + independent review) per CLAUDE.md.

---

## 7. Rollout
1. Land A (session gate) first — it stands alone and fixes bug #1 immediately.
2. Land D (realized ledger + recap) — independent, fixes bugs #2/#3.
3. Land B (orchestrator + budget lane), then C (queue + open re-check) on top of A.
4. Full `pytest tests/runner/` green; confirm prod ledgers/tasks unchanged.
5. Restart the runner; watch one closed-window wave + the next open re-check live.
