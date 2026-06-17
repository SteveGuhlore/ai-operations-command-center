# Tony — 2nd-Pass Analyst Dashboard · Repo Handoff

Two files in this package:

- **Tony-standalone.html** — the finished dashboard as a single self-contained file (fonts + runtime + all logic inlined). Open it directly in a browser to see the target design and behavior. Use it as the visual/behavioral reference, or embed it and feed it real data via the contract below.
- **HANDOFF.md** — this file. Paste the block below into the repo Claude session (the one with both the bot/scanner repo and the Tony agent repo loaded).

This is a RESEARCH SIMULATION / paper account. Keep all "research simulation only — not investment advice" disclaimers; never present it as profitable or as advice.

---

## Paste this into the repo session

```
CONTEXT
We have a finished front-end dashboard for "Tony" — a second-pass stock analyst that sits on top of our automated Alpaca paper-trading scanner ("the bot"). It's a single self-contained HTML file (Tony-standalone.html) — no framework, vanilla JS, inline styles. It currently runs on SIMULATED data and has clearly-marked LIVE/SIM states throughout. Your job: hard-wire it into our VM + Alpaca keys and complete the real-data integration. This is a RESEARCH SIMULATION / paper account — keep all "research simulation only — not investment advice" disclaimers intact; never present it as profitable or as advice.

WHAT THE DASHBOARD ALREADY EXPECTS (the data contract — don't redesign it, just feed it)
The page reads an optional global config and falls back to simulation if absent:
  window.TONY_FEED = {
    alpacaKey:    "...",   // market-DATA key (read-only)
    alpacaSecret: "...",
    proxyUrl:     "/api/spx",     // optional: returns { closes: number[] } for SPY
    proxyName:    "our-vm"        // optional label
  }
Resolution order already implemented in fetchSPX(): Alpaca data API -> proxyUrl -> keyless Stooq -> simulated. Position marks (updateMarks()) hit Alpaca latest-trades for the open symbols when keys are present. Live ET clock + market-open/closed are already computed client-side.

INTEGRATION TASKS
1) Serve the dashboard from our app/VM (static route is fine).
2) DO NOT ship Alpaca secrets to the browser. Instead add two backend routes on the VM that use the repo's existing keys server-side:
     GET /api/spx        -> { closes: number[] }            // ~15 daily SPY closes, last value = latest (last close when market closed)
     GET /api/marks?syms=AXON,DHR,... -> { trades: { SYM: { p: number } } }   // mirror Alpaca's latest-trades shape
   Then set window.TONY_FEED = { proxyUrl: "/api/spx" } and point updateMarks() at /api/marks. Keys stay on the VM.
3) Replace the remaining simulated datasets with live/persisted data from our DB: equity curve (Tony vs bot vs SPY, indexed to a common $1M start — do NOT re-base SPY to a synthetic flat line; use last close when market is closed), the paper book, today's P&L attribution, the calls feed, the calibration buckets, the override hit-rate (24 saved / 25 missed style), and the closed-trade log.
4) Keep the SIM/LIVE indicators honest: when a feed is unavailable, the dashboard already dashes the SPY line and shows "awaiting live feed" — preserve that behavior; never let missing data render as a real -X% move.

TIMELINE / HORIZON FEATURE (both repos work together)
The bot repo owns the mechanical baseline; the Tony repo owns the override. Add a projection object to any verdict that carries a price target:
  projection: {
    target: number,
    botHorizonDays: [min, max],   // computed in the BOT repo: distance-to-target / ATR(14), widened by realized vol
    horizonDays:    [min, max],   // the TONY 2nd pass revises it: keep / tighten / or set projection:null if standing aside
    basis: string,                // one-line rationale, e.g. "~3xATR to target at current RVOL"
    confidence: number            // 0..1
  }
Never output calendar dates — only trading-day ranges from now. The dashboard drawer already plots last->target across this horizon; once projection is real, it reflects Tony's actual estimate (and we can add the bot's as a faint reference line).

GUARDRAILS
- Additive only: don't change existing call schemas beyond adding `projection`; keep it backward-compatible and null-safe so calls without a target still render.
- This touches no order execution, position sizing, or risk logic — keep it that way. Open a branch/PR, don't commit to main.
- Tests: (1) horizon scales inversely with ATR; (2) Tony's range is flagged when it diverges >50% from the bot's; (3) a verdict with no target yields projection:null; (4) /api/spx returns last close (not base) when the market is closed.
```

---

## Quick map of the dashboard internals (for the integrator)

- **fetchSPX()** — benchmark resolution chain (Alpaca → proxy → Stooq → sim). Returns `{ src, closes }`.
- **applyLiveSPX(closes)** — resamples to the chart's point count and indexes to the common $1M start. Caches last good closes in `localStorage['tony_spx']` and never reverts to a synthetic line.
- **updateMarks()** — per-symbol last-price marks for the paper book (Alpaca latest-trades; needs keys/proxy).
- **tickClock() / marketOpen()** — live ET clock + market session state.
- **buildChart()** — equity series geometry, axes, and max-drawdown computation.
- Views: `state.view` ∈ `overview | calls | positions`. Tabs swap panes; masthead (equity, stats, risk strip) persists.
- All copy text and single colors are editable in place; everything else is driven by the data above.
