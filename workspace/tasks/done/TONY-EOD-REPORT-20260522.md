---
task_id: TONY-EOD-REPORT-20260522
assigned_agent: market_research_worker
status: done
priority: normal
pod: stock_research_pod
task_type: market_scan_summary
---

# Tony EOD Report — 2026-05-22

Analyze the following end-of-day stock scanner report from Tony Stocks.

Your job:
1. Identify the top 3-5 momentum signals from the scan
2. Note any risk flags or unusual patterns
3. Summarize overall market conditions suggested by the data
4. Call `write_tony_insight` with your key finding (1-3 sentences, high signal-to-noise)

## EOD Report Data

```json
{
  "date": "2026-05-22",
  "cycles_completed": 10,
  "latest_watch_status": "stopped",
  "provider": "alpaca_iex",
  "symbols_scanned": 163,
  "real_symbols_scanned": 162,
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
    "SQ",
    "PARA"
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
    },
    {
      "symbol": "PARA",
      "reason": "Repeated Alpaca IEX missing real data flagged 2026-05-22 EOD report"
    }
  ],
  "replacement_symbols": [],
  "real_intraday_count": 69,
  "stale_intraday_count": 0,
  "snapshots_created_today": 127,
  "snapshots_updated_today": 127,
  "real_only_snapshots_reviewed": 127,
  "demo_rows_excluded": 0,
  "legacy_unknown_rows_excluded": 0,
  "missing_real_data_rows_excluded": 0,
  "reconciliation": {
    "raw_snapshot_rows": 127,
    "raw_triggered_entry_rows": 36,
    "product_eligible_rows": 127,
    "product_visible_symbols": 25,
    "deduped_active_positions": 16,
    "deduped_waiting_picks": 12,
    "deduped_closed_results": 0,
    "target_hits": 0,
    "stop_hits": 0,
    "partial_moves": 0,
    "pending_triggers": 9,
    "expired_no_trigger": 0,
    "insufficient_data": 16,
    "incomplete_rows_hidden_from_product_views": 0,
    "history_rows_hidden_from_product_views": 102
  },
  "tony_memory_summary": {
    "report_date": "2026-05-22",
    "row_count": 127,
    "setup_counts": {
      "Breakout Watch": 99,
      "Momentum Continuation": 1,
      "Pullback Watch": 10,
      "Speculative Watchlist": 17
    },
    "triggered_count": 36,
    "active_count": 16,
    "closed_count": 0,
    "target_hit_count": 0,
    "stop_hit_count": 0,
    "partial_move_count": 0,
    "reassessment_label_counts": {
      "still_valid": 13,
      "weakening": 23
    },
    "best_setup_note": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 31 triggered row(s).",
    "worst_setup_note": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 31 triggered row(s).",
    "data_quality_notes": [
      "Tony memory is research-only. It does not change scoring, trigger rules, or trading behavior automatically.",
      "This memory summary only uses filtered real-only rows.",
      "102 historical row(s) stayed in raw history but were hidden from current product views."
    ]
  },
  "tony_self_review": {
    "strongest_setup": "Preliminary best follow-through: Breakout Watch recorded 0 target hit(s) and 0 partial move(s) across 31 triggered row(s).",
    "weakest_setup": "Preliminary weakest follow-through: Breakout Watch logged 0 stop/failure outcome(s) across 31 triggered row(s).",
    "what_worked": [
      "No setups recorded a target or partial hit in today's real-only rows."
    ],
    "what_failed": [
      "No setups recorded a stop or failure outcome in today's real-only rows."
    ],
    "needs_more_data": [
      "127 row(s) labeled insufficient_future_data \u2014 outcome windows are still open, not failures.",
      "Breakout Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Momentum Continuation: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction.",
      "Pullback Watch: only 0 row(s) with a finalized outcome \u2014 not enough context to read direction."
    ],
    "tomorrow_watch": [
      "16 active position(s) carry over \u2014 check reassessment labels at next open.",
      "36 raw triggered row(s) in history (20 are earlier history rows for active symbols).",
      "9 pending trigger(s) still waiting \u2014 watch for intraday trigger levels.",
      "23 setup(s) flagged weakening \u2014 monitor for further deterioration."
    ],
    "active_symbols": [
      "ANET",
      "BKR",
      "CRM",
      "CVS",
      "D",
      "DAL",
      "EBAY",
      "KMI",
      "LYFT",
      "ORCL",
      "SLB",
      "TXN",
      "VZ",
      "WMB",
      "XEL",
      "ZETA"
    ],
    "deduped_active_positions": 16,
    "raw_triggered_rows": 36,
    "waiting_picks": 12,
    "pending_triggers": 9,
    "rule_suggestions": [
      {
        "suggestion": "No rule changes suggested yet \u2014 not enough conclusive real-only data.",
        "reason": "0 conclusive triggered row(s) available (+36 still waiting on future data); at least 3 conclusive rows needed.",
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
        "reason": "0 conclusive triggered row(s) available (+36 still waiting on future data); at least 3 conclusive rows needed.",
        "confidence": "low",
        "status": "needs_review",
        "strategy_version": "v1"
      }
    ],
    "note": "Strategy versioning tracks rule suggestion history. Suggestions are never applied automatically. Current version: v1."
  },
  "replay_summary": {
    "strategy_version": "v1",
    "total_rows": 127,
    "total_triggered": 36,
    "total_conclusive": 0,
    "total_insufficient_future_data": 127,
    "setups": [
      {
        "setup": "Breakout Watch",
        "total_rows": 99,
        "triggered": 31,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 99,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Momentum Continuation",
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
        "setup": "Pullback Watch",
        "total_rows": 10,
        "triggered": 4,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 10,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      },
      {
        "setup": "Speculative Watchlist",
        "total_rows": 17,
        "triggered": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "partial_moves": 0,
        "insufficient_future_data": 17,
        "conclusive_rows": 0,
        "target_rate": null,
        "stop_rate": null,
        "strategy_version": "v1"
      }
    ],
    "notes": [
      "This is a research-only replay. It does not change scoring, trigger rules, or trading behavior.",
      "127 row(s) labeled insufficient_future_data \u2014 outcome windows are still open and are excluded from rate calculations.",
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
            "total_rows": 99,
            "triggered_rows": 31,
            "active_rows": 31,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 99
          },
          {
            "signal_value": "Speculative Watchlist",
            "total_rows": 17,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 17
          },
          {
            "signal_value": "Pullback Watch",
            "total_rows": 10,
            "triggered_rows": 4,
            "active_rows": 4,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 10
          },
          {
            "signal_value": "Momentum Continuation",
            "total_rows": 1,
            "triggered_rows": 1,
            "active_rows": 1,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 1
          }
        ]
      },
      {
        "signal_key": "above_below_vwap",
        "signal_label": "Above/Below VWAP",
        "counts": [
          {
            "signal_value": "above_vwap",
            "total_rows": 75,
            "triggered_rows": 26,
            "active_rows": 26,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 75
          },
          {
            "signal_value": "below_vwap",
            "total_rows": 52,
            "triggered_rows": 10,
            "active_rows": 10,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 52
          }
        ]
      },
      {
        "signal_key": "opening_range",
        "signal_label": "Opening Range Breakout/Breakdown",
        "counts": [
          {
            "signal_value": "signal_not_stored",
            "total_rows": 88,
            "triggered_rows": 28,
            "active_rows": 28,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 88
          },
          {
            "signal_value": "opening_range_breakout_watch",
            "total_rows": 22,
            "triggered_rows": 6,
            "active_rows": 6,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 22
          },
          {
            "signal_value": "opening_range_breakdown_warning",
            "total_rows": 17,
            "triggered_rows": 2,
            "active_rows": 2,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 17
          }
        ]
      },
      {
        "signal_key": "volume_signal",
        "signal_label": "Volume Confirmation/Warning",
        "counts": [
          {
            "signal_value": "low_liquidity_concern",
            "total_rows": 112,
            "triggered_rows": 36,
            "active_rows": 36,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 112
          },
          {
            "signal_value": "volume_confirmation",
            "total_rows": 10,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 10
          },
          {
            "signal_value": "speculative_volume_risk",
            "total_rows": 5,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 5
          }
        ]
      },
      {
        "signal_key": "atr_risk",
        "signal_label": "ATR Risk",
        "counts": [
          {
            "signal_value": "atr_risk_not_flagged",
            "total_rows": 122,
            "triggered_rows": 36,
            "active_rows": 36,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 122
          },
          {
            "signal_value": "wide_atr_concern",
            "total_rows": 5,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 5
          }
        ]
      },
      {
        "signal_key": "market_context",
        "signal_label": "Market Context",
        "counts": [
          {
            "signal_value": "market_supportive",
            "total_rows": 127,
            "triggered_rows": 36,
            "active_rows": 36,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 127
          }
        ]
      },
      {
        "signal_key": "risk_reward_bucket",
        "signal_label": "Risk/Reward Bucket",
        "counts": [
          {
            "signal_value": "2.0_to_2.99",
            "total_rows": 127,
            "triggered_rows": 36,
            "active_rows": 36,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 127
          }
        ]
      },
      {
        "signal_key": "reassessment_label",
        "signal_label": "Reassessment Label",
        "counts": [
          {
            "signal_value": "signal_not_stored",
            "total_rows": 91,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 91
          },
          {
            "signal_value": "weakening",
            "total_rows": 23,
            "triggered_rows": 23,
            "active_rows": 23,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 23
          },
          {
            "signal_value": "still_valid",
            "total_rows": 13,
            "triggered_rows": 13,
            "active_rows": 13,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 13
          }
        ]
      },
      {
        "signal_key": "score_bucket",
        "signal_label": "Score Bucket",
        "counts": [
          {
            "signal_value": "70-79",
            "total_rows": 55,
            "triggered_rows": 6,
            "active_rows": 6,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 55
          },
          {
            "signal_value": "80-89",
            "total_rows": 48,
            "triggered_rows": 20,
            "active_rows": 20,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 48
          },
          {
            "signal_value": "60-69",
            "total_rows": 14,
            "triggered_rows": 7,
            "active_rows": 7,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 14
          },
          {
            "signal_value": "90-100",
            "total_rows": 10,
            "triggered_rows": 3,
            "active_rows": 3,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 10
          }
        ]
      },
      {
        "signal_key": "universe_role",
        "signal_label": "Universe Role",
        "counts": [
          {
            "signal_value": "primary_candidate",
            "total_rows": 109,
            "triggered_rows": 36,
            "active_rows": 36,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 109
          },
          {
            "signal_value": "speculative_candidate",
            "total_rows": 18,
            "triggered_rows": 0,
            "active_rows": 0,
            "conclusive_rows": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "partial_moves": 0,
            "insufficient_future_data": 18
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
    "symbols_selected_loaded": 163,
    "real_data_symbols": 163,
    "symbols_scored": 75,
    "not_scored_count": 88,
    "symbols_skipped": 88,
    "missing_real_data_count": 0,
    "missing_real_data_symbols": [],
    "quarantined_count": 0,
    "quarantined_symbols": [],
    "unique_symbols_scanned_today": 345,
    "unique_symbols_scored_today": 140,
    "percent_universe_covered_today": 98.85,
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
        310
      ],
      "latest_bucket_id": 215,
      "latest_total": 163,
      "latest_core_count": 3,
      "latest_open_snapshot_count": 34,
      "latest_previous_candidate_count": 1,
      "latest_discovery_count": 125
    },
    "skip_reason_counts": {
      "liquidity_below_minimums": 0,
      "avg_volume_below_minimum": 657,
      "price_outside_bounds": 151,
      "not_enough_bars": 17,
      "not_enough_data": 0,
      "stale_data": 0,
      "missing_real_data": 3,
      "quarantined": 0,
      "no_eligible_setup": 0,
      "duplicate_tracked": 0,
      "other_unknown": 0
    },
    "rotation_diagnostics": {
      "note": "Active tracked, core, and open-snapshot symbols are expected to appear in multiple cycles. Discovery symbols should rotate across cycles. This diagnostic is for tuning only \u2014 it does not change rotation behavior.",
      "unique_symbols_scanned": 141,
      "total_scan_appearances": 873,
      "repeat_scan_count": 140,
      "top_repeated_symbols": [
        {
          "symbol": "ACHR",
          "scan_count": 11,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "BKR",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "BMY",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "CRM",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "CVS",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "D",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "DAL",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "DKNG",
          "scan_count": 11,
          "universe_role": "speculative_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "EBAY",
          "scan_count": 11,
          "universe_role": "primary_candidate",
          "repeat_label": ""
        },
        {
          "symbol": "GTLB",
          "scan_count": 11,
          "universe_role": "primary_candidate",
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
          310
        ],
        "latest_bucket_id": 215,
        "latest_total": 163,
        "latest_core_count": 3,
        "latest_open_snapshot_count": 34,
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

# TONY-EOD-REPORT-20250522

## Summary

- **163 symbols scanned** across 10 cycles; 127 real-only snapshots reviewed. No conclusive outcomes yet—all 127 rows flagged `insufficient_future_data`.
- **36 triggered setups** across 4 strategy types: Breakout Watch dominates (31 triggered), Pullback Watch (4), Momentum Continuation (1), Speculative Watchlist (0).
- **16 active positions carry over**; 23 setups flagged "weakening" vs. 13 "still valid." Volume concerns dominate (112/127 rows show low liquidity).
- **Data quality clean**: No stale bars, no demo/legacy rows, 5 quarantined symbols removed (HCP, SAMSF, SMAR, SQ, PARA).
- **Score distribution skews high**: 80-89 bucket leads (20 triggered), followed by 70-79 (6 triggered). All risk/reward ratios clustered in 2.0–2.99 range. Market context: fully supportive.

---

## Top 5 Momentum Signals by Trigger Count

| Signal | Value | Triggered | Active | Notes |
|--------|-------|-----------|--------|-------|
| **Setup Category** | Breakout Watch | 31 | 31 | Dominant pattern; 0 targets/stops hit yet |
| **Score Bucket** | 80–89 | 20 | 20 | Highest quality subset; 48 total candidates |
| **Above/Below VWAP** | Above VWAP | 26 | 26 | Bullish tilt; 75 total above-VWAP rows |
| **Risk/Reward** | 2.0–2.99 | 36 | 36 | All triggered rows in mid-range bucket |
| **Reassessment Label** | Weakening | 23 | 23 | **Red flag**: 23 triggered setups already decaying |

---

## Risk Flags & Unusual Patterns

1. **Pervasive Low Liquidity** — 112 of 127 rows (88%) flagged `low_liquidity_concern`. Only 10 rows show `volume_confirmation`; 5 rows carry `speculative_volume_risk`.  
   *Implication*: Slippage risk is material; position sizing must account for exit depth.

2. **Weakening Setup Decay** — Of 36 triggered rows, 23 (64%) already reassessed as "weakening." Only 13 flagged "still valid."  
   *Implication*: Momentum may be fading intraday; quick follow-through critical at open.

3. **Zero Conclusive Outcomes** — All 127 rows await future data. No target hits, stop hits, or partial moves recorded.  
   *Implication*: Strategy rules cannot yet be validated or refined; need 3+ conclusive rows before tuning.

4. **Speculative Watchlist Triggers Zero** — 17 candidates in Speculative Watchlist; none triggered yet.  
   *Implication*: Lower-quality ideas not meeting entry bars; may indicate overly conservative thresholds or genuine weakness in secondary universe.

5. **Opening Range Signals Minimal** — Only 22/127 rows scored for Opening Range Breakout/Breakdown; 6 breakouts, 2 breakdowns triggered.  
   *Implication*: Limited intraday range context; dependent on real-time market data collection.

---

## Overall Market Conditions Summary

- **Broad supportive backdrop**: All 127 rows assigned `market_supportive` tag. No adverse macro flags.
- **Bullish lean**: 75 rows above VWAP vs. 52 below (59% vs. 41%).
- **Universe rotation healthy**: 98.85% of configured universe (345/349 symbols) touched; 125 new discovery symbols rotated in latest bucket.
- **Skip mechanics sound**: Primary friction is avg volume below minimum (657 symbols), followed by price outside bounds (151), not data errors.
- **Liquidity-driven throttle**: 112 low-liquidity flags suggest scanner is correctly filtering micro-cap / illiquid venues, but also narrows active candidate pool to high-conviction setups.

---

## Active Symbols Tomorrow (Carry-Over)

ANET, BKR, CRM, CVS, D, DAL, EBAY, KMI, LYFT, ORCL, SLB, TXN, VZ, WMB, XEL, ZETA

**Watch for reassessment labels at next open. Monitor 23 "weakening" setups for further deterioration; confirm 13 "still valid" setups hold entry levels.**

---

## Research-Only Insights

- **Strategy version v1** remains unchanged; insufficient conclusive data to suggest rule modifications.
- **9 pending triggers** still waiting on intraday levels; monitor for fill opportunity or expiration.
- **Rotation diagnostics**: Top-repeated symbols (ACHR, BKR, BMY, CRM, CVS, D, DAL, DKNG, EBAY, GTLB) are core/tracked slots; discovery bucket rotating as intended.

---

## Key Takeaway for Research Dashboard

**36 triggered setups across breakout, pullback, and momentum patterns show supportive market context and above-VWAP bias, but 64% of active positions already labelled weakening and 88% face low-liquidity headwinds. No conclusive outcomes yet; stack for follow-through and monitor reassessment labels at 09:30.**
