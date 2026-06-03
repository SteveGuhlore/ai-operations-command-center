# Handoff — Tony Stocks Loop + "Cockpit" Dashboard

**Date:** 2026-06-02
**From:** Command Center session (Stephen + Claude)
**To:** TradingBotAgentProject Claude session
**Status:** Command-Center side of the loop is wired and verified. This doc is what the *trading-bot* side must guarantee, plus the kickoff for the Cockpit overhaul.

---

## 0. TL;DR

The two-agent loop is: **Tony (scanner, your project) → bridge file → Tony Stocks (Command Center) → verdict written back**.

The Command Center now ingests your **markdown bridge** (`bridge/tony-stocks/YYYY-MM-DD.md`) into a daily task for Tony Stocks. For the loop to run tomorrow and every day, your project must do **two** things reliably (§1). For the Cockpit dashboard's dual-agent view to work, the Command Center must emit a **structured second-layer record** that does not exist yet (§3) — that's the real build dependency.

---

## 1. The bridge contract (DO NOT BREAK — the loop depends on it)

Each trading day, after the close, the trading bot must write **one** markdown file to:

```
<CommandCenter>/bridge/tony-stocks/YYYY-MM-DD.md
```

(That folder is read every runner cycle by `runner/bridge/tony_bridge.py::_scan_markdown_bridge`. The Command Center repo path on this machine is `C:\Users\alexa\Downloads\AI Operations Command Center`. If the two repos ever move, set env `TONY_BRIDGE_DIR` on the Command Center side to point at wherever you write these files.)

**Required:** filename stem is exactly the ISO date (`2026-06-03.md`); `index.md` and any non-date-named file are ignored. Frontmatter should include `date`, `source`, `export_type` (the current format is correct — keep it). The body is consumed verbatim as the brief, so keep the Tier 1 / Tier 2 / Tier 3, Cluster Risk Flags, and "For Tony" sections — Tony Stocks acts on them directly.

**Dedup:** one file per date = one brief. Re-writing the same date does **not** create a second task (dedup keyed on `YYYY-MM-DD/daily_brief` in `workspace/logs/tony-bridge-processed.json`). If you need to force a re-run for a date, that key must be removed from the processed log on the Command Center side.

**Legacy JSON path (still supported as fallback):** `../TradingBotAgentProject/reports/<date>/{eod_report,strategy_proposal,approval_package}.json`. If a markdown bridge exists for a date, it wins; JSON is only used for dates with no markdown. You can stop writing JSON if you want — markdown is the primary path now.

### What "broken" looks like
- No file dropped for the date → no brief → Tony Stocks silent that day.
- File named with anything other than the bare date → silently skipped.
- Wrong folder → silently skipped (no error).

---

## 2. What the Command Center already does (verified 2026-06-02)

- `tony_bridge.py` reads the markdown bridge and creates `workspace/tasks/todo/TONY-DAILY-BRIEF-<YYYYMMDD>.md`, routed to `market_research_worker` (Tony Stocks, `gemini-2.5-pro`).
- Tony Stocks runs his workflow (signal ledger, ticker memory, web research, macro/sector overlay) and writes insights back via `write_tony_insight` → `agent_insights.json` in your reports dir.
- Tests: `tests/runner/test_tony_bridge.py` (6 passing) cover JSON path, markdown path, dedup, and markdown-wins-on-conflict.

**Runner must be running** for any of this to fire. It is started by `python scripts/launch.py --interval 600` (dashboard on :8765 + cron loop every 10 min). Install the logon autostart with `powershell -File scripts/install-autostart.ps1` so it survives reboots. If the runner is down, bridge files just queue up and process when it next starts.

---

## 3. Cockpit dependency — the structured second-layer record (THE build blocker)

Per the design spec §7, the Cockpit's hero feature is **two agents racing**: each pick shows Tony's score/plan **and** Tony Stocks' independent **score + verdict**, and the Track Record page overlays **two** equity curves. Today Tony Stocks only emits **free-text** insights:

```jsonc
// agent_insights.json (current — NOT enough for the Cockpit)
{ "date": "2026-05-23", "category": "momentum", "insight": "GTLB 4-day continuation...",
  "confidence": "high", "symbols": ["GTLB"], "status": "new" }
```

The Cockpit needs a **per-pick, structured verdict** keyed to the scanner's pick. Proposed contract (the Command Center should emit this; consume it read-only in the Cockpit, and render "... awaiting handoff" when a pick has no record yet):

```jsonc
// proposed: tony_stocks_verdicts.json  (one object per pick Tony Stocks reviews)
{
  "date": "2026-06-03",
  "symbol": "ZETA",
  "scanner_score": 88.75,          // Tony's score, echoed for alignment
  "tony_stocks_score": 72,         // independent 0-100
  "verdict": "adjust",             // enum: reaffirm | adjust | pass | override | close
  "reasoning": "Earnings 6/11 inside the hold window; trim target to +10%.",
  "evidence": ["earnings_date", "sector_lag_XLK", "news:guidance_cut"],
  "returned_pct": null,            // filled later when outcome known; null until then
  "handoff_age_min": 14,           // minutes from scanner pick to this verdict
  "schema_version": 1
}
```

Plus a **second track record** so the agreement matrix and dual equity curve have data:

```jsonc
// proposed: tony_stocks_record.json
{ "since": "2026-06-01", "win_rate": 0.0, "avg_r": 0.0, "target_hits": 0, "stop_hits": 0,
  "equity_series": [ { "date": "2026-06-01", "equity": 10000 } ],
  "agreement": { "agreed_right": 0, "agreed_wrong": 0, "override_saved": 0, "override_missed": 0 } }
```

**Recommendation:** this is a small Command-Center follow-up task — add a `write_tony_verdict(symbol, score, verdict, reasoning, ...)` tool next to `write_tony_insight`, and have Tony Stocks call it once per Tier-1 ticker. Until it exists, build every Cockpit second-layer slot against the typed contract above and **degrade gracefully** (the spec already mandates this). The Cockpit overhaul must not block on it and must not break without it.

---

## 4. Cockpit overhaul — where it lives & first move

The Cockpit (Next.js 16 / React 19 / Tailwind 4, the `dashboard-web` in the spec) is **your project's** surface, not the Command Center's (the Command Center only has a Python FastAPI dashboard on :8765). Build it there.

Suggested first slice (matches spec §11 phasing):
1. Visual tokens + `StatusBar` + route collapse to `/` (Board) and `/record`.
2. `BoardTable` + `PlanRail` reading Tony's existing picks/prices (Tony layer only — no CC data needed yet).
3. `DeepDive` + `PlanChart` (candles + volume + plan lines).
4. Track Record (Tony layer).
5. **Then** wire the second-layer slots to `tony_stocks_verdicts.json` / `tony_stocks_record.json` from §3, behind the typed contract, with "... awaiting handoff" fallbacks.

Guardrails from the spec hold: no profit claims, no false-precision ETA line, read-only/advisory (no order entry), WCAG AA + 44px targets on the new palette.

---

## 5. Open question for Stephen

The §3 structured-verdict contract is the one real new dependency. Decide who builds the emitter: **Command Center** (add `write_tony_verdict` here — recommended, since Tony Stocks already runs here) vs. the trading bot deriving it from the free-text insights (lossy). Recommendation: Command Center emits it.
