---
task_id: TONY-EOD-REPORT-20260519
assigned_agent: market_research_worker
status: done
priority: normal
pod: stock_research_pod
task_type: market_scan_summary
---

# Tony EOD Report — 2026-05-19

Analyze the following end-of-day stock scanner report from Tony Stocks.

Your job:
1. Identify the top 3-5 momentum signals from the scan
2. Note any risk flags or unusual patterns
3. Summarize overall market conditions suggested by the data
4. Call `write_tony_insight` with your key finding (1-3 sentences, high signal-to-noise)

## EOD Report Data

```json
{
  "date": "2026-05-19",
  "cycles_completed": 16,
  "latest_watch_status": "stopped",
  "provider": "alpaca_iex",
  "symbols_scanned": 167,
  "real_symbols_scanned": 163,
  "api_requests": 3,
  "fallback_symbols": [
    "CFLT",
    "CYBR",
    "LAZR",
    "TRUE"
  ],
  "missing_real_data_symbols": [
    "CFLT",
    "CYBR",
    "LAZR",
    "TRUE"
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
  "real_intraday_count": 62,
  "stale_intraday_count": 0,
  "snapshots_created_today": 75,
  "snapshots_updated_today": 75,
  "real_only_snapshots_reviewed": 75,
  "demo_rows_excluded": 0,
  "legacy_unknown_rows_excluded": 0,
  "missing_real_data_rows_excluded": 0,
  "reconciliation": {
    "raw_snapshot_rows": 75,
    "raw_triggered_entry_rows": 16,
    "product_eligible_rows": 75,
    "product_visible_symbols": 19,
    "deduped_active_positions": 6,
    "deduped_waiting_picks": 9,
    "deduped_closed_results": 4,
    "target_hits": 0,
    "stop_hits": 0,
    "partial_moves": 0,
    "pending_triggers": 0,
    "expired_no_trigger": 0,
    "insufficient_data": 10,
    "incomplete_rows_hidden_from_product_views": 0,
    "history_rows_hidden_from_product_views": 56
  },
  "tony_memory_summary": {
    "report_date": "2026-05-19",
    "row_count": 75,
    "setup_counts": {
      "Breakout Watch": 32,
      "Momentum Continuation": 3,
      "Pullback Watch": 5,
      "Speculative Watchlist": 35
    },
    "triggered_count": 16,
    "active_count": 6,
    "closed_count": 4,
    "target_hit_count": 0,
    "stop_hit_count": 0,
    "partial_move_count": 0,
    "reassessment_label_counts": {
      "still_valid": 11,
      "weakening": 5
    },
    "best_setup_note": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 10 triggered row(s).",
    "worst_setup_note": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 10 triggered row(s).",
    "data_quality_notes": [
      "Tony memory is research-only. It does not change scoring, trigger rules, or trading behavior automatically.",
      "This memory summary only uses filtered real-only rows.",
      "56 historical row(s) stayed in raw history but were hidden from current product views."
    ]
  },
  "tony_self_review": {
    "strongest_setup": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 10 triggered row(s).",
    "weakest_setup": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 10 triggered row(s).",
    "what_worked": [
      "No setups recorded a target or partial hit in today's real-only rows."
    ],
    "what_failed": [
      "No setups recorded a stop or failure outcome in today's real-only rows."
    ],
    "needs_more_data": [
      "75 row(s) labeled insufficient_future_data \u2014 outcome windows are still open, not failures.",
      "Breakout Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Momentum Continuation: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Pullback Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction."
    ],
    "tomorrow_watch": [
      "6 active position(s) carry over \u2014 check reassessment labels at next open.",
      "16 raw triggered row(s) in history (10 are earlier history rows for active symbols).",
      "5 setup(s) flagged weakening \u2014 monitor for further deterioration."
    ],
    "active_symbols": [
      "ARM",
      "DVN",
      "DXCM",
      "GTLB",
      "OXY",
      "PATH"
    ],
    "deduped_active_positions": 6,
    "raw_triggered_rows": 16,
    "waiting_picks": 9,
    "pending_triggers": 0,
    "rule_suggestions": [
      {
        "suggestion": "No rule changes suggested yet \u2014 not enough conclusive real-only data.",
        "reason": "0 conclusive triggered row(s) available (+16 still waiting on future data); at least 3 conclusive rows needed.",
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
        "reason": "0 conclusive triggered row(s) available (+16 still waiting on future data); at least 3 conclusive rows needed.",
        "confidence": "low",
        "status": "needs_review",
        "strategy_version": "v1"
      }
    ],
    "note": "Strategy versioning tracks rule suggestion history. Suggestions are never applied automatically. Current version: v1."
  },
  "replay_summary": {
    "strategy_version": "v1",
    "total_rows": 75,
    "total_triggered": 16,
    "total_conclusive": 0,
    "total_insufficient_future_data": 75,
    "setups": [
      {
        "setup": "Breakout Watch",
        "total_rows": 32,
        "triggered": 10,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 32,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Momentum Continuation",
        "total_rows": 3,
        "triggered": 2,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 3,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Pullback Watch",
        "total_rows": 5,
        "triggered": 4,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 5,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Speculative Watchlist",
        "total_rows": 35,
        "triggered": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 35,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      }
    ],
    "notes": [
      "This is a research-only replay. It does not change scoring, trigger rules, or trading behavior.",
      "75 row(s) labeled insufficient_future_data \u2014 outcome windows are still open and are excluded from rate calculations.",
      "No conclusive outcomes yet. All rates are unavailable until future market data is collected."
    ]
  }
}
```


## Agent Output

## Summary

- **163 real symbols scanned** across 75 snapshots with 16 triggered entries; 4 symbols quarantined due to data feed issues (HCP, SAMSF, SMAR, SQ).
- **Setup distribution**: Breakout Watch dominates (32 rows, 10 triggered); Speculative Watchlist (35 rows, 0 triggered); Momentum Continuation (3 rows, 2 triggered); Pullback Watch (5 rows, 4 triggered).
- **No conclusive outcomes yet**: All 75 rows lack sufficient future data; 0 target hits, 0 stop hits, 0 partial moves recorded to date.
- **Active carry-over**: 6 deduped positions (ARM, DVN, DXCM, GTLB, OXY, PATH) + 9 waiting picks; 5 setups flagged as weakening.
- **Data quality**: 56 historical rows hidden from product views; no rule changes recommended (v1 strategy) due to insufficient conclusive data (0 conclusive rows; threshold is 3+).

---

## Setup Breakdown

| Setup Type | Total Rows | Triggered | Target Hits | Stop Hits | Status |
|---|---|---|---|---|---|
| Breakout Watch | 32 | 10 | 0 | 0 | Awaiting outcomes |
| Speculative Watchlist | 35 | 0 | 0 | 0 | No triggers yet |
| Pullback Watch | 5 | 4 | 0 | 0 | Awaiting outcomes |
| Momentum Continuation | 3 | 2 | 0 | 0 | Awaiting outcomes |

---

## Risk Flags & Data Issues

1. **Four symbols in quarantine** (HCP, SAMSF, SMAR, SQ): Missing real data on Alpaca IEX feed; legacy/delisted/OTC status. Remove from active scanning or source alternate feeds.
2. **No finalized outcomes**: All 75 rows classified as insufficient_future_data. Market impact and setup efficacy cannot yet be assessed; too early for rule validation.
3. **Five setups weakening**: Monitor reassessment labels at next open; potential early deterioration signals.
4. **56 historical rows hidden**: Data hygiene acceptable, but confirms system is managing legacy carryover properly.

---

## Market Conditions Inferred

- **Breakout Watch is the primary active signal**: 10 triggered rows suggest breakout conditions are live, but lack of target/stop fills indicates tight consolidation or low follow-through volatility.
- **Speculative Watchlist dormant**: 0 triggers on 35 rows suggests limited high-conviction speculative setups or elevated caution in market environment.
- **Pullback Watch elevated**: 4 of 5 rows triggered indicates pullback opportunity recognition, consistent with healthy trend correction context.

---

## Insight for Trading Dashboard

**write_tony_insight**: *Scan generated 16 real-triggered entries across three active setup types (Breakout Watch, Pullback Watch, Momentum Continuation) with no outcomes concluded; all 75 rows require additional market data. Carry-over: 6 active positions + 5 weakening setups warrant reassessment at next open; no rule suggestions until 3+ conclusive outcomes accumulate.*
