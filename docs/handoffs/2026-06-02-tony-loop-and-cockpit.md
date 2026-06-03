# Handoff — Tony Stocks Two-Layer Loop (Command Center ⇄ Trading Bot)

**Date:** 2026-06-02 (updated after second-layer tools shipped)
**From:** Command Center session (Stephen + Claude)
**To:** TradingBotAgentProject Claude session
**Purpose:** Get both projects on the same page. This is the complete contract: how the
handoff executes, what the Command Center now produces, and exactly what it needs back.

---

## 0. The loop in one picture

```
 TRADING BOT (Layer 1)                COMMAND CENTER (Layer 2 — "Tony Stocks")
 scanner, charts, technical    ──►   bridge/tony-stocks/YYYY-MM-DD.md
 scores, target/stop                       │  (runner ingests every ~10 min)
                                           ▼
                                   TONY-DAILY-BRIEF task → Tony (gemini-2.5-pro)
                                   pulls live financials (yfinance) + news (Brave),
                                   forms his OWN score + verdict per pick
                                           │
              ┌────────────────────────────┴───────────────────────────┐
              ▼                                                          ▼
   agent_insights.json (free-text)              tony_stocks_verdicts.json (STRUCTURED)
              │                                                          │
              └──────────────►  TRADING BOT / COCKPIT read these  ◄──────┘
                                           ▲
        (Phase 3 dependency)  tony_stocks_outcomes.json  ── BOT MUST EMIT ──┘
```

Layer 1 = scripts/quant. Layer 2 = a reasoning agent that independently researches and
**reaffirms / adjusts / overrides** the bot's picks, and (next) learns from outcomes.

---

## 1. INBOUND — the bridge contract (bot → Command Center) — DO NOT BREAK

Each trading day, after the close, write **one** markdown file to:

```
<CommandCenter>/bridge/tony-stocks/YYYY-MM-DD.md
```

Repo path on this machine: `C:\Users\alexa\Downloads\AI Operations Command Center`.
If repos move, set env `TONY_BRIDGE_DIR` on the Command Center side to your output dir.

- **Filename** = bare ISO date (`2026-06-03.md`). `index.md` / any non-date file is ignored.
- **Frontmatter**: `date`, `source`, `export_type` (current format is correct — keep it).
- **Body is consumed verbatim** as Tony's brief. Keep the **Tier 1 / Tier 2 / Tier 3**,
  **Cluster Risk Flags**, and **"For Tony"** sections. Tony deep-analyzes every Tier-1 ticker.
- **Dedup**: one file per date = one brief. Re-writing a date does NOT re-spawn (dedup key
  `YYYY-MM-DD/daily_brief` in `workspace/logs/tony-bridge-processed.json`). To force a
  re-run, that key must be removed on the CC side.
- **Cadence**: drop once per trading day. No file = Tony is silent that day (correct: no new data).
- **Silent-skip traps**: wrong folder, or filename not a bare date → skipped with no error.

**Legacy JSON path** (`../TradingBotAgentProject/reports/<date>/*.json`) still works as a
fallback for dates with no markdown, but **markdown is primary** — you can stop writing JSON.

---

## 2. How ingestion executes (Command Center side — for your awareness)

- Every runner cycle (~10 min via `scripts/launch.py --interval 600`),
  `runner/bridge/tony_bridge.py::scan_and_process` scans the bridge dir.
- New date → spawns **one** `TONY-DAILY-BRIEF-<date>` task → `market_research_worker`
  (Tony Stocks, gemini-2.5-pro).
- **Trigger model = handoff-spawned, one task per bridge file.** No standing queue; Atlas is
  forbidden from spawning Tony tasks. (Roadmap will add per-ticker fan-out + a weekly
  self-review task, but the daily trigger stays handoff-driven.)
- The runner must be running for any of this to fire.

---

## 3. OUTBOUND — what the Command Center now produces (bot & Cockpit consume)

### 3a. `agent_insights.json` (existing) — free-text commentary
```jsonc
{ "date":"2026-06-03", "category":"momentum", "insight":"...", "confidence":"high",
  "symbols":["GTLB"], "status":"new" }
```

### 3b. `tony_stocks_verdicts.json` (NEW — BUILT & VERIFIED) — the structured second layer
One object per Tier-1 pick Tony reviews. **This is the typed contract the Cockpit dual-agent
view + Track Record read.** Lives beside `agent_insights.json` in your `reports/` dir
(override with env `TONY_VERDICTS_FILE`).
```jsonc
{
  "date": "2026-06-03",
  "symbol": "GTLB",
  "tony_score": 30,             // Tony's INDEPENDENT 0–100 conviction
  "scanner_score": 75.01,       // echoed from the bridge, for head-to-head
  "verdict": "override",        // reaffirm | adjust | override | pass | close
  "thesis": "Earnings after the bell today; analyst target below price; high short float.",
  "target": null,               // Tony's own target (set on adjust/override)
  "stop": null,                 // Tony's own stop
  "evidence": ["earnings_today","analyst_target_below_price","high_short_float"],
  "catalysts": "Q2 earnings 2026-06-02",
  "earnings_date": "2026-06-02",
  "confidence": "high",
  "returned_pct": null,         // ← filled later from YOUR outcomes feed (§4)
  "schema_version": 1,
  "status": "new"
}
```
Verified live 2026-06-02: OXY → `reaffirm` (Tony 82 vs scanner 73); GTLB → `override` (Tony 30).

---

## 4. WHAT WE NEED FROM THE BOT

### 4a. Keep dropping the daily bridge (§1). This is the whole trigger.

### 4b. NEW — emit OUTCOMES so Tony can learn (the Phase-3 dependency)
Today Tony's verdicts are written but **never graded** — `returned_pct` stays null forever,
so he can't learn whether his overrides actually beat the scanner. The bot already tracks
paper outcomes; please emit them in a stable file the Command Center can read:

```
../TradingBotAgentProject/reports/tony_stocks_outcomes.json   (or set TONY_OUTCOMES_FILE)
```
```jsonc
[{
  "symbol": "GTLB",
  "pick_date": "2026-06-03",      // the date of the bridge/verdict this resolves (JOIN KEY)
  "result": "stop_hit",           // target_hit | stop_hit | closed | expired
  "entry": 25.56,
  "exit": 23.21,
  "return_pct": -9.2,
  "days_held": 4,
  "resolved_date": "2026-06-09"
}]
```

### 4c. The JOIN KEY (critical — read this)
Tony's verdicts are keyed by **(symbol, date)** where `date` = the bridge date he reviewed.
Outcomes must carry a **`pick_date`** that equals the bridge date the pick originated on, so
the Command Center can match each outcome to the right verdict and stamp `returned_pct` +
grade it (was the verdict right?). If you assign a stable per-pick ID in the bridge instead,
include that same ID on the outcome and tell us the field name — either works, but it must be
deterministic.

### 4d. Cockpit (your project's Next.js `dashboard-web`)
The Cockpit lives in YOUR repo (CC only has the Python dashboard on :8765). It now has real
data to render: read `tony_stocks_verdicts.json` for the dual-score + verdict per pick, and
(once 4b lands) compute the second track record + agreement matrix. Degrade to "… awaiting
handoff" when a pick has no verdict yet.

---

## 5. Quick reference — files & envs

| File | Direction | Owner | Env override |
|---|---|---|---|
| `bridge/tony-stocks/YYYY-MM-DD.md` | bot → CC | bot writes | `TONY_BRIDGE_DIR` (CC) |
| `reports/agent_insights.json` | CC → bot | CC writes | `TONY_INSIGHTS_FILE` |
| `reports/tony_stocks_verdicts.json` | CC → bot/Cockpit | CC writes | `TONY_VERDICTS_FILE` |
| `reports/tony_stocks_outcomes.json` | **bot → CC** | **bot writes (4b)** | `TONY_OUTCOMES_FILE` |

## 6. Your action items (trading-bot terminal)
1. Confirm the daily bridge keeps dropping in the §1 format.
2. Build/emit `tony_stocks_outcomes.json` per §4b with the §4c join key. **This is the one
   real new dependency** — it unlocks Tony's learning loop.
3. Point the Cockpit's second-layer at `tony_stocks_verdicts.json` (degrade gracefully).
4. Reply with: the exact path you'll write outcomes to, and the join field (pick_date vs an ID).
