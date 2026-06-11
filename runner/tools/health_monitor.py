"""Operator health alerts — warn (Telegram) when the book/verdicts drift into a known-bad state,
so problems surface before they bite instead of being noticed by eye. Read-only + fail-soft.

Watches for the failure modes behind the June 2026 incident:
- a verdict backlog (the daily pre-open flush failed, so verdicts stacked up), and
- an oversized/pyramided position (market value well above the per-entry target).
"""
import json
import os
from pathlib import Path


def _load_verdicts() -> list:
    from runner.ledger.alpaca_paper import VERDICTS_FILE
    try:
        data = json.loads(Path(VERDICTS_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def collect_issues(positions: list | None = None, verdicts: list | None = None) -> list:
    """Return human-readable health issues (empty list = healthy). The daily 9:25 flush should
    leave only TODAY's verdicts, so verdicts spanning MORE THAN ONE date mean the flush failed and
    a backlog is building (the precursor to the June 2026 pyramiding). A raw count is intentionally
    NOT used — whole-universe daily deep-dives legitimately produce ~150 verdicts in a single day."""
    from runner.ledger.alpaca_paper import ENTRY_NOTIONAL
    from runner.ledger.market_clock import trading_day
    oversize_mult = float(os.environ.get("TONY_OVERSIZE_ALERT_MULT", "1.6"))

    issues: list = []
    if verdicts is None:
        verdicts = _load_verdicts()
    # Real backlog = a verdict dated BEFORE today (ET) still in the file — the daily flush should
    # leave only today's. A bare "spans >1 date" false-fires on a legitimate next-day verdict the
    # evening research wave wrote that simply hasn't been flushed yet.
    today = trading_day()
    stale = sorted({d for x in verdicts if (d := x.get("date")) and d < today})
    if stale:
        issues.append(f"Verdict backlog: {len(verdicts)} verdicts including stale date(s) {stale} "
                      f"(before today {today}) — the daily pre-open flush may have failed.")

    if positions is None:
        from runner.tools.tony_book import read_book_cache
        positions = (read_book_cache() or {}).get("positions") or []
    for p in positions:
        # COST BASIS (qty x avg_entry), not market value: pyramiding doubles the share count while a
        # winner just appreciates — using current_price flags every big winner as "oversized". Fall
        # back to current_price only when entry is missing.
        try:
            qty = float(p.get("qty") or 0)
            entry = p.get("avg_entry_price")
            px = float(entry if entry is not None else (p.get("current_price") or 0))
        except (TypeError, ValueError):
            continue
        cost = qty * px
        if cost > oversize_mult * ENTRY_NOTIONAL:
            issues.append(f"Oversized position {p.get('symbol')}: cost basis ${cost:,.0f} "
                          f"(~{cost / ENTRY_NOTIONAL:.1f}x the ${ENTRY_NOTIONAL:,.0f} entry) — possible pyramiding.")
    return issues
