---
task_id: TONY-EOD-REPORT-20260520
assigned_agent: market_research_worker
status: done
priority: normal
pod: stock_research_pod
task_type: market_scan_summary
---

# Tony EOD Report — 2026-05-20

Analyze the following end-of-day stock scanner report from Tony Stocks.

Your job:
1. Identify the top 3-5 momentum signals from the scan
2. Note any risk flags or unusual patterns
3. Summarize overall market conditions suggested by the data
4. Call `write_tony_insight` with your key finding (1-3 sentences, high signal-to-noise)

## EOD Report Data

```json
{
  "date": "2026-05-20",
  "cycles_completed": 14,
  "latest_watch_status": "stopped",
  "provider": "alpaca_iex",
  "symbols_scanned": 151,
  "real_symbols_scanned": 147,
  "api_requests": 3,
  "fallback_symbols": [
    "CYBR",
    "LAZR",
    "TRUE",
    "CFLT"
  ],
  "missing_real_data_symbols": [
    "CYBR",
    "LAZR",
    "TRUE",
    "CFLT"
  ],
  "configured_quarantined_symbols": [
    "HCP",
    "SAMSF",
    "SMAR",
    "SQ"
  ],
  "configured_quarantine_entries": [
    {
      "symbol": "HCP",
      "reason": "Repeated Alpaca IEX no-bar / missing real data (legacy HashiCorp ticker on research list)"
    },
    {
      "symbol": "SAMSF",
      "reason": "Repeated Alpaca IEX missing real data (OTC / limited IEX coverage)"
    },
    {
      "symbol": "SMAR",
      "reason": "Repeated Alpaca IEX missing real data (acquired; delisted from active tape)"
    },
    {
      "symbol": "SQ",
      "reason": "Repeated Alpaca IEX missing real data (symbol may not resolve on IEX feed)"
    }
  ],
  "replacement_symbols": [],
  "real_intraday_count": 58,
  "stale_intraday_count": 0,
  "snapshots_created_today": 26,
  "snapshots_updated_today": 26,
  "real_only_snapshots_reviewed": 26,
  "demo_rows_excluded": 0,
  "legacy_unknown_rows_excluded": 0,
  "missing_real_data_rows_excluded": 0,
  "reconciliation": {
    "raw_snapshot_rows": 26,
    "raw_triggered_entry_rows": 3,
    "product_eligible_rows": 26,
    "product_visible_symbols": 7,
    "deduped_active_positions": 2,
    "deduped_waiting_picks": 5,
    "deduped_closed_results": 0,
    "target_hits": 0,
    "stop_hits": 0,
    "partial_moves": 0,
    "pending_triggers": 2,
    "expired_no_trigger": 0,
    "insufficient_data": 2,
    "incomplete_rows_hidden_from_product_views": 0,
    "history_rows_hidden_from_product_views": 19
  },
  "tony_memory_summary": {
    "report_date": "2026-05-20",
    "row_count": 26,
    "setup_counts": {
      "Breakout Watch": 15,
      "Pullback Watch": 1,
      "Speculative Watchlist": 10
    },
    "triggered_count": 3,
    "active_count": 2,
    "closed_count": 0,
    "target_hit_count": 0,
    "stop_hit_count": 0,
    "partial_move_count": 0,
    "reassessment_label_counts": {
      "still_valid": 2,
      "weakening": 1
    },
    "best_setup_note": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 2 triggered row(s).",
    "worst_setup_note": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 2 triggered row(s).",
    "data_quality_notes": [
      "Tony memory is research-only. It does not change scoring, trigger rules, or trading behavior automatically.",
      "This memory summary only uses filtered real-only rows.",
      "19 historical row(s) stayed in raw history but were hidden from current product views."
    ]
  },
  "tony_self_review": {
    "strongest_setup": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 2 triggered row(s).",
    "weakest_setup": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 2 triggered row(s).",
    "what_worked": [
      "No setups recorded a target or partial hit in today's real-only rows."
    ],
    "what_failed": [
      "No setups recorded a stop or failure outcome in today's real-only rows."
    ],
    "needs_more_data": [
      "26 row(s) labeled insufficient_future_data \u2014 outcome windows are still open, not failures.",
      "Breakout Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Pullback Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction."
    ],
    "tomorrow_watch": [
      "2 active position(s) carry over \u2014 check reassessment labels at next open.",
      "3 raw triggered row(s) in history (1 are earlier history rows for active symbols).",
      "2 pending trigger(s) still waiting \u2014 watch for intraday trigger levels.",
      "1 setup(s) flagged weakening \u2014 monitor for further deterioration."
    ],
    "active_symbols": [
      "GTLB",
      "ZETA"
    ],
    "deduped_active_positions": 2,
    "raw_triggered_rows": 3,
    "waiting_picks": 5,
    "pending_triggers": 2,
    "rule_suggestions": [
      {
        "suggestion": "No rule changes suggested yet \u2014 not enough conclusive real-only data.",
        "reason": "0 conclusive triggered row(s) available (+3 still waiting on future data); at least 3 conclusive rows needed.",
        "confidence": "low",
        "status": "needs_review",
        "strategy_version": "v1"
      }
    ],
    "research_only": true
  },
  "strategy_version_report": {
    "current_version": "v1",
    "pending_suggestions": 1,
    "status_counts": {
      "needs_review": 1
    },
    "suggestions": [
      {
        "suggestion": "No rule changes suggested yet \u2014 not enough conclusive real-only data.",
        "reason": "0 conclusive triggered row(s) available (+3 still waiting on future data); at least 3 conclusive rows needed.",
        "confidence": "low",
        "status": "needs_review",
        "strategy_version": "v1"
      }
    ],
    "note": "Strategy versioning tracks rule suggestion history. Suggestions are never applied automatically. Current version: v1."
  },
  "replay_summary": {
    "strategy_version": "v1",
    "total_rows": 26,
    "total_triggered": 3,
    "total_conclusive": 0,
    "total_insufficient_future_data": 26,
    "setups": [
      {
        "setup": "Breakout Watch",
        "total_rows": 15,
        "triggered": 2,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 15,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Pullback Watch",
        "total_rows": 1,
        "triggered": 1,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 1,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Speculative Watchlist",
        "total_rows": 10,
        "triggered": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 10,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      }
    ],
    "notes": [
      "This is a research-only replay. It does not change scoring, trigger rules, or trading behavior.",
      "26 row(s) labeled insufficient_future_data \u2014 outcome windows are still open and are excluded from rate calculations.",
      "No conclusive outcomes yet. All rates are unavailable until future market data is collected."
    ]
  }
}
```


## Agent Output

## Summary

- **Scan Coverage**: 147 real symbols processed across 151 configured (4 fallback symbols missing data; 4 configured quarantined). 26 real-only snapshots reviewed with no stale intraday bars.
- **Setup Distribution**: Breakout Watch dominates (15 rows, 2 triggered); Speculative Watchlist (10 rows, 0 triggered); Pullback Watch (1 row, 1 triggered). Total 3 triggered entries across all setups.
- **Active Positions**: 2 carries forward (GTLB, ZETA). 5 waiting picks in queue. 2 pending triggers still open.
- **Outcome Status**: All 26 rows insufficient future data — zero conclusive results yet. No target hits, stop hits, or partial moves recorded to date.
- **Data Quality**: No stale bars; 19 historical rows hidden from product views. Quarantine list stable (HCP, SAMSF, SMAR, SQ remain delisted/OTC/unresolved on IEX feed).

---

## Top Momentum Signals

**No conclusive signal strength rankings available.** All 26 rows remain open with insufficient future data. Raw trigger count by setup:

1. **Breakout Watch** — 2 triggered (out of 15 rows) — monitoring for follow-through
2. **Pullback Watch** — 1 triggered (out of 1 row) — lone entry awaiting outcome
3. **Speculative Watchlist** — 0 triggered (out of 10 rows) — no entry yet

---

## Risk Flags & Unusual Patterns

- **Data Gaps**: 4 symbols (CYBR, LAZR, TRUE, CFLT) failed real-data retrieval; quarantine list includes 4 additional unresolved tickers (HCP, SAMSF, SMAR, SQ). No replacement candidates identified.
- **Insufficient Maturity**: 26/26 rows (100%) lack outcome windows. Cannot assess win/loss rates or confirm setup validity.
- **Weak Breakout Follow-Through**: Breakout Watch triggered 2 entries but shows 0 target/partial hits and 0 stop hits—suggests entries either still open or lacked conviction.
- **Reassessment Flag**: 1 setup labeled "weakening" — monitor for deterioration into next session.
- **Rule Confidence**: Strategy suggestion pending (low confidence; needs ≥3 conclusive rows to recommend changes).

---

## Overall Market Conditions

Scan reflects an **early-stage accumulation window** with limited decision data:
- Moderate trigger rate (3/26 = 11.5%) suggests selective entry conditions.
- Absence of target or stop outcomes indicates positions are either very new or market conditions have stalled momentum follow-through.
- Active symbol list (GTLB, ZETA) should be monitored at next open for reassessment labels and trigger updates.

---

## Call to write_tony_insight

**Key Finding**: All 26 real-only snapshots from 2026-05-20 remain open with insufficient future data; 3 triggered entries (2 Breakout Watch, 1 Pullback Watch) show no target, stop, or partial outcomes yet. Recommend tracking active carries (GTLB, ZETA) and 2 pending triggers into session 2026-05-21 before updating setup efficacy.
