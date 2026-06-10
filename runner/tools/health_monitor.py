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
    oversize_mult = float(os.environ.get("TONY_OVERSIZE_ALERT_MULT", "1.6"))

    issues: list = []
    if verdicts is None:
        verdicts = _load_verdicts()
    dates = sorted({x.get("date") for x in verdicts if x.get("date")})
    if len(dates) > 1:
        issues.append(f"Verdict backlog: {len(verdicts)} verdicts spanning {len(dates)} dates "
                      f"({dates}) — the daily pre-open flush may have failed.")

    if positions is None:
        from runner.tools.tony_book import read_book_cache
        positions = (read_book_cache() or {}).get("positions") or []
    for p in positions:
        try:
            mv = float(p.get("qty") or 0) * float(p.get("current_price") or 0)
        except (TypeError, ValueError):
            continue
        if mv > oversize_mult * ENTRY_NOTIONAL:
            issues.append(f"Oversized position {p.get('symbol')}: ${mv:,.0f} "
                          f"(~{mv / ENTRY_NOTIONAL:.1f}x the ${ENTRY_NOTIONAL:,.0f} target).")
    return issues
