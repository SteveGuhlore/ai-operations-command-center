---
task_id: TONY-EOD-REPORT-20260521
assigned_agent: market_research_worker
status: done
priority: normal
pod: stock_research_pod
task_type: market_scan_summary
---

# Tony EOD Report — 2026-05-21

Analyze the following end-of-day stock scanner report from Tony Stocks.

Your job:
1. Identify the top 3-5 momentum signals from the scan
2. Note any risk flags or unusual patterns
3. Summarize overall market conditions suggested by the data
4. Call `write_tony_insight` with your key finding (1-3 sentences, high signal-to-noise)

## EOD Report Data

```json
{
  "date": "2026-05-21",
  "cycles_completed": 12,
  "latest_watch_status": "stopped",
  "provider": "alpaca_iex",
  "symbols_scanned": 164,
  "real_symbols_scanned": 163,
  "api_requests": 3,
  "fallback_symbols": [
    "PARA"
  ],
  "missing_real_data_symbols": [
    "PARA"
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
  "real_intraday_count": 67,
  "stale_intraday_count": 0,
  "snapshots_created_today": 129,
  "snapshots_updated_today": 129,
  "real_only_snapshots_reviewed": 129,
  "demo_rows_excluded": 0,
  "legacy_unknown_rows_excluded": 0,
  "missing_real_data_rows_excluded": 0,
  "reconciliation": {
    "raw_snapshot_rows": 129,
    "raw_triggered_entry_rows": 30,
    "product_eligible_rows": 129,
    "product_visible_symbols": 21,
    "deduped_active_positions": 9,
    "deduped_waiting_picks": 18,
    "deduped_closed_results": 0,
    "target_hits": 0,
    "stop_hits": 0,
    "partial_moves": 0,
    "pending_triggers": 12,
    "expired_no_trigger": 0,
    "insufficient_data": 9,
    "incomplete_rows_hidden_from_product_views": 0,
    "history_rows_hidden_from_product_views": 108
  },
  "tony_memory_summary": {
    "report_date": "2026-05-21",
    "row_count": 129,
    "setup_counts": {
      "Breakout Watch": 88,
      "Pullback Watch": 14,
      "Speculative Watchlist": 27
    },
    "triggered_count": 30,
    "active_count": 9,
    "closed_count": 0,
    "target_hit_count": 0,
    "stop_hit_count": 0,
    "partial_move_count": 0,
    "reassessment_label_counts": {
      "still_valid": 14,
      "weakening": 16
    },
    "best_setup_note": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 26 triggered row(s).",
    "worst_setup_note": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 26 triggered row(s).",
    "data_quality_notes": [
      "Tony memory is research-only. It does not change scoring, trigger rules, or trading behavior automatically.",
      "This memory summary only uses filtered real-only rows.",
      "108 historical row(s) stayed in raw history but were hidden from current product views."
    ]
  },
  "tony_self_review": {
    "strongest_setup": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 26 triggered row(s).",
    "weakest_setup": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 26 triggered row(s).",
    "what_worked": [
      "No setups recorded a target or partial hit in today's real-only rows."
    ],
    "what_failed": [
      "No setups recorded a stop or failure outcome in today's real-only rows."
    ],
    "needs_more_data": [
      "129 row(s) labeled insufficient_future_data \u2014 outcome windows are still open, not failures.",
      "Breakout Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Pullback Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction."
    ],
    "tomorrow_watch": [
      "9 active position(s) carry over \u2014 check reassessment labels at next open.",
      "30 raw triggered row(s) in history (21 are earlier history rows for active symbols).",
      "12 pending trigger(s) still waiting \u2014 watch for intraday trigger levels.",
      "16 setup(s) flagged weakening \u2014 monitor for further deterioration."
    ],
    "active_symbols": [
      "BMY",
      "CVS",
      "D",
      "DAL",
      "LRCX",
      "NOW",
      "ORCL",
      "VZ",
      "ZETA"
    ],
    "deduped_active_positions": 9,
    "raw_triggered_rows": 30,
    "waiting_picks": 18,
    "pending_triggers": 12,
    "rule_suggestions": [
      {
        "suggestion": "No rule changes suggested yet \u2014 not enough conclusive real-only data.",
        "reason": "0 conclusive triggered row(s) available (+30 still waiting on future data); at least 3 conclusive rows needed.",
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
        "reason": "0 conclusive triggered row(s) available (+30 still waiting on future data); at least 3 conclusive rows needed.",
        "confidence": "low",
        "status": "needs_review",
        "strategy_version": "v1"
      }
    ],
    "note": "Strategy versioning tracks rule suggestion history. Suggestions are never applied automatically. Current version: v1."
  },
  "replay_summary": {
    "strategy_version": "v1",
    "total_rows": 129,
    "total_triggered": 30,
    "total_conclusive": 0,
    "total_insufficient_future_data": 129,
    "setups": [
      {
        "setup": "Breakout Watch",
        "total_rows": 88,
        "triggered": 26,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 88,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Pullback Watch",
        "total_rows": 14,
        "triggered": 4,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 14,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Speculative Watchlist",
        "total_rows": 27,
        "triggered": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 27,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      }
    ],
    "notes": [
      "This is a research-only replay. It does not change scoring, trigger rules, or trading behavior.",
      "129 row(s) labeled insufficient_future_data \u2014 outcome windows are still open and are excluded from rate calculations.",
      "No conclusive outcomes yet. All rates are unavailable until future market data is collected."
    ]
  },
  "signal_scorecard": {
    "note": "Signal attribution is preliminary and needs more real-market days before any conclusion should be drawn. This scorecard is reporting only.",
    "signals": [
      {
        "signal_key": "setup_category",
        "signal_label": "Setup Category",
        "counts": [
          {
            "signal_value": "Breakout Watch",
            "total_rows": 88,
            "triggered_rows": 26,
            "active_rows": 26,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 88
          },
          {
            "signal_value": "Speculative Watchlist",
            "total_rows": 27,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 27
          },
          {
            "signal_value": "Pullback Watch",
            "total_rows": 14,
            "triggered_rows": 4,
            "active_rows": 4,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 14
          }
        ]
      },
      {
        "signal_key": "above_below_vwap",
        "signal_label": "Above/Below VWAP",
        "counts": [
          {
            "signal_value": "above_vwap",
            "total_rows": 68,
            "triggered_rows": 21,
            "active_rows": 21,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 68
          },
          {
            "signal_value": "below_vwap",
            "total_rows": 61,
            "triggered_rows": 9,
            "active_rows": 9,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 61
          }
        ]
      },
      {
        "signal_key": "opening_range",
        "signal_label": "Opening Range Breakout/Breakdown",
        "counts": [
          {
            "signal_value": "signal_not_stored",
            "total_rows": 63,
            "triggered_rows": 18,
            "active_rows": 18,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 63
          },
          {
            "signal_value": "opening_range_breakout_watch",
            "total_rows": 38,
            "triggered_rows": 12,
            "active_rows": 12,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 38
          },
          {
            "signal_value": "opening_range_breakdown_warning",
            "total_rows": 28,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 28
          }
        ]
      },
      {
        "signal_key": "volume_signal",
        "signal_label": "Volume Confirmation/Warning",
        "counts": [
          {
            "signal_value": "low_liquidity_concern",
            "total_rows": 122,
            "triggered_rows": 30,
            "active_rows": 30,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 122
          },
          {
            "signal_value": "volume_confirmation",
            "total_rows": 4,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 4
          },
          {
            "signal_value": "speculative_volume_risk",
            "total_rows": 3,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 3
          }
        ]
      },
      {
        "signal_key": "atr_risk",
        "signal_label": "ATR Risk",
        "counts": [
          {
            "signal_value": "atr_risk_not_flagged",
            "total_rows": 113,
            "triggered_rows": 30,
            "active_rows": 30,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 113
          },
          {
            "signal_value": "wide_atr_concern",
            "total_rows": 16,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 16
          }
        ]
      },
      {
        "signal_key": "market_context",
        "signal_label": "Market Context",
        "counts": [
          {
            "signal_value": "market_supportive",
            "total_rows": 129,
            "triggered_rows": 30,
            "active_rows": 30,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 129
          }
        ]
      },
      {
        "signal_key": "risk_reward_bucket",
        "signal_label": "Risk/Reward Bucket",
        "counts": [
          {
            "signal_value": "2.0_to_2.99",
            "total_rows": 129,
            "triggered_rows": 30,
            "active_rows": 30,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 129
          }
        ]
      },
      {
        "signal_key": "reassessment_label",
        "signal_label": "Reassessment Label",
        "counts": [
          {
            "signal_value": "signal_not_stored",
            "total_rows": 99,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 99
          },
          {
            "signal_value": "weakening",
            "total_rows": 16,
            "triggered_rows": 16,
            "active_rows": 16,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 16
          },
          {
            "signal_value": "still_valid",
            "total_rows": 14,
            "triggered_rows": 14,
            "active_rows": 14,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 14
          }
        ]
      },
      {
        "signal_key": "score_bucket",
        "signal_label": "Score Bucket",
        "counts": [
          {
            "signal_value": "70-79",
            "total_rows": 52,
            "triggered_rows": 12,
            "active_rows": 12,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 52
          },
          {
            "signal_value": "80-89",
            "total_rows": 31,
            "triggered_rows": 12,
            "active_rows": 12,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 31
          },
          {
            "signal_value": "60-69",
            "total_rows": 30,
            "triggered_rows": 3,
            "active_rows": 3,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 30
          },
          {
            "signal_value": "90-100",
            "total_rows": 16,
            "triggered_rows": 3,
            "active_rows": 3,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 16
          }
        ]
      },
      {
        "signal_key": "universe_role",
        "signal_label": "Universe Role",
        "counts": [
          {
            "signal_value": "primary_candidate",
            "total_rows": 102,
            "triggered_rows": 30,
            "active_rows": 30,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 102
          },
          {
            "signal_value": "speculative_candidate",
            "total_rows": 27,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 27
          }
        ]
      }
    ]
  },
  "terminal_outcome_summary": {
    "note": "Terminal P/L is research-only and uses stored tracking stop/target levels, not actual filled prices. It does not represent trading performance.",
    "terminal_count": 0,
    "stop_hit": {},
    "target_hit": {},
    "other_closed": {},
    "inferred_exit_price_count": 0
  },
  "scan_coverage": {
    "configured_universe_size": 349,
    "symbols_selected_loaded": 164,
    "real_data_symbols": 164,
    "symbols_scored": 84,
    "not_scored_count": 80,
    "symbols_skipped": 80,
    "missing_real_data_count": 0,
    "missing_real_data_symbols": [],
    "quarantined_count": 0,
    "quarantined_symbols": [],
    "unique_symbols_scanned_today": 343,
    "unique_symbols_scored_today": 140,
    "percent_universe_covered_today": 98.28,
    "api_requests": 3,
    "batch_requests": 2,
    "rotation_bucket_summary": {
      "bucket_ids_today": [
        0,
        30,
        60,
        90,
        125,
        155,
        185,
        215,
        250,
        280,
        310,
        340
      ],
      "latest_bucket_id": 340,
      "latest_total": 164,
      "latest_core_count": 3,
      "latest_open_snapshot_count": 35,
      "latest_previous_candidate_count": 1,
      "latest_discovery_count": 125
    },
    "skip_reason_counts": {
      "liquidity_below_minimums": 0,
      "avg_volume_below_minimum": 448,
      "price_outside_bounds": 104,
      "not_enough_bars": 16,
      "not_enough_data": 0,
      "stale_data": 0,
      "missing_real_data": 1,
      "quarantined": 9,
      "no_eligible_setup": 330,
      "duplicate_tracked": 0,
      "other_unknown": 0
    },
    "rotation_diagnostics": {
      "note": "Active tracked, core, and open-snapshot symbols are expected to appear in multiple cycles. Discovery symbols should rotate across cycles. This diagnostic is for tuning only \u2014 it does not change rotation behavior.",
      "unique_symbols_scanned": 141,
      "total_scan_appearances": 930,
      "repeat_scan_count": 141,
      "top_repeated_symbols": [
        {
          "symbol": "AMD",
          "scan_count": 12,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "ARM",
          "scan_count": 12,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "CLSK",
          "scan_count": 12,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "DKNG",
          "scan_count": 12,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "DVN",
          "scan_count": 12,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "DXCM",
          "scan_count": 12,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "GTLB",
          "scan_count": 12,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "IWM",
          "scan_count": 12,
          "universe_role": "benchmark",
          "repeat_label": ""
        },
        {
          "symbol": "JOBY",
          "scan_count": 12,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "MARA",
          "scan_count": 12,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        }
      ],
      "active_core_repeats": [],
      "estimated_fresh_discovery": 125,
      "percent_universe_touched": 40.4,
      "rotation_bucket_summary": {
        "bucket_ids_today": [
          0,
          30,
          60,
          90,
          125,
          155,
          185,
          215,
          250,
          280,
          310,
          340
        ],
        "latest_bucket_id": 340,
        "latest_total": 164,
        "latest_core_count": 3,
        "latest_open_snapshot_count": 35,
        "latest_previous_candidate_count": 1,
        "latest_discovery_count": 125
      },
      "symbols_never_scanned_today": null
    },
    "notes": [
      "Active/core/prior/open-snapshot symbols may repeat across cycles, so daily unique coverage will be lower than raw cycle totals.",
      "The discovery bucket should rotate across cycles; this report only measures coverage and does not change rotation behavior.",
      "A larger universe needs a screener funnel before scanning thousands of stocks end to end."
    ]
  }
}
```


## Agent Output

## Summary

- **Scan Coverage:** 163 real symbols scanned across 12 cycles; 98.3% of universe touched. 84 symbols scored; 30 triggered setups identified.
- **Active Positions:** 9 deduped active positions (BMY, CVS, D, DAL, LRCX, NOW, ORCL, VZ, ZETA) carry into 2026-05-22.
- **Setup Distribution:** Breakout Watch dominates (88 total rows, 26 triggered); Pullback Watch (14 rows, 4 triggered); Speculative Watchlist (27 rows, 0 triggered).
- **Signal Quality:** 122 rows flagged low liquidity concern; 21 setups above VWAP (higher triggering rate); 16 setups reassessed as weakening. All 129 rows lack conclusive future data.
- **Risk Flags:** No target hits, stop hits, or partial moves recorded yet—outcome windows remain open. 12 pending triggers await intraday levels. Four symbols quarantined due to data gaps (HCP, SAMSF, SMAR, SQ).

---

## Setup Ranking by Trigger Momentum

| Setup | Total Rows | Triggered | Trigger Rate | Reassessment Status |
|-------|-----------|-----------|--------------|-------------------|
| **Breakout Watch** | 88 | 26 | 29.5% | 14 still valid, 16 weakening |
| **Pullback Watch** | 14 | 4 | 28.6% | Mostly unassessed |
| **Speculative Watchlist** | 27 | 0 | 0% | No triggers yet |

**Key observation:** Breakout Watch is the only setup with live triggers. Pullback Watch shows comparable trigger efficiency on smaller sample. Speculative Watchlist has not crossed trigger threshold as of EOD.

---

## Signal Strength Analysis

**Highest Conviction Signals:**
1. **Above VWAP** (68 rows, 21 triggered) — Price above VWAP correlates with 31% trigger rate; below VWAP only 15% trigger rate.
2. **Opening Range Breakout Watch** (38 rows, 12 triggered) — 32% trigger rate on intraday breakout patterns.
3. **Score Bucket 70–89** (83 combined rows, 24 triggered) — Mid-range scores drive 29% aggregate trigger rate; 90+ scores only 19%.

**Risk Flags:**
- **Low Liquidity Concern:** 122/129 rows (94%) flagged. All 30 triggered setups carry liquidity risk.
- **Wide ATR Concern:** 16 rows unscored; no triggers. Volatility floor may be filtering candidates.
- **Weakening Label:** 16 triggered rows reassessed as weakening—monitor for continued deterioration at next open.

---

## Market Context & Data Quality

- **Market Sentiment:** All 129 rows show "market_supportive" context; broad market backdrop not hostile.
- **Risk/Reward:** 100% of setups in 2.0–2.99 RR bucket—uniform, conservative ratio targeting.
- **Universe Role:** 102 primary candidates triggered (30/102); 27 speculative candidates not triggered. Primary universe outperforming speculative.

**Data Maturity Issue:**
- **129/129 rows insufficient_future_data** — Outcome windows still open; no terminal P/L available.
- **0 conclusive rows** — Strategy backtest cannot yet assess target/stop efficacy.
- **Rule Suggestion Status:** "needs_review" but marked low confidence; requires ≥3 conclusive outcomes before rule changes recommended.

---

## Tomorrow's Watch List

| Priority | Item | Count | Action |
|----------|------|-------|--------|
| **P1** | Active position reassessment | 9 symbols | Check still_valid vs. weakening labels at open |
| **P2** | Pending triggers | 12 setups | Monitor intraday levels; watch for fills |
| **P3** | Weakening setups | 16 rows | Assess trend deterioration; consider early exits |
| **P4** | Historical rollover | 30 triggered rows | Review entry fills; reconcile with current price |

---

## Data Quality Notes

- **Quarantine Impact:** 4 symbols removed (HCP, SAMSF, SMAR, SQ) due to repeated no-bar/missing IEX data. PARA returned no real data today but not yet quarantined.
- **Snapshot Health:** 129 created, 129 updated; 0 stale intraday rows. Real-time data feed stable.
- **Skip Reasons:** 448 symbols below avg volume minimum; 104 outside price bounds; 330 no eligible setup match.
- **Rotation Coverage:** 141 unique symbols across 930 scan appearances; ~40% of 349-symbol universe touched. Discovery bucket rotating as intended.

---

## Research Conclusion

**Setup Status:** Breakout Watch is the only live momentum signal; 26 triggered rows await outcome data over next 2–5 trading days. Pullback Watch secondary tier shows same efficiency. Speculative Watchlist inactive—criteria too stringent or market conditions not supportive. All risk/reward uniform; no outlier setups. Low liquidity pervasive; accept as operational constraint or tighten volume minimums.

---

## Insight for Trading Dashboard

**Key Finding:**  
Breakout Watch generated 26 triggered entries on 2026-05-21 in a supportive market environment, all below 2.5x risk/reward targets and 94% flagged with low liquidity; however, no terminal outcomes are available yet—outcome windows remain open across 129 total rows, preventing rule-strength assessment until Friday EOD or later.
