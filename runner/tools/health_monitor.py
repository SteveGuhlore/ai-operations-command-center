"""Operator health alerts — warn (Telegram) when the book/verdicts drift into a known-bad state,
so problems surface before they bite instead of being noticed by eye. Read-only + fail-soft.

Watches for the failure modes behind the June 2026 incident:
- a verdict backlog (the daily pre-open flush failed, so verdicts stacked up), and
- an oversized/pyramided position (market value well above the per-entry target).
"""
import json
import os
from pathlib import Path


def _verdict_count() -> int:
    from runner.ledger.alpaca_paper import VERDICTS_FILE
    try:
        data = json.loads(Path(VERDICTS_FILE).read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return 0


def collect_issues(positions: list | None = None, verdict_count: int | None = None) -> list:
    """Return human-readable health issues (empty list = healthy). Pure given its inputs; the
    defaults read live state (verdicts file + book cache) so the caller can just call it."""
    from runner.ledger.alpaca_paper import ENTRY_NOTIONAL
    backlog = int(os.environ.get("TONY_VERDICT_BACKLOG_ALERT", "60"))
    oversize_mult = float(os.environ.get("TONY_OVERSIZE_ALERT_MULT", "1.6"))

    issues: list = []
    vc = _verdict_count() if verdict_count is None else verdict_count
    if vc > backlog:
        issues.append(f"Verdict backlog: {vc} verdicts queued (the daily pre-open flush may have failed).")

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
