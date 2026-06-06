"""tony_realized — Tony's own realized-trade ledger (Component D).

Bugs #2/#3: the daily recap graded Tony's verdicts against the BOT's scanner outcomes and showed
no P/L, so his actual stop-outs were invisible. This persists every position Tony closes (target /
stop / discretionary close) to workspace/tony-realized.json and aggregates a today + all-time
summary the recap and self-review read. CC-internal, additive — the bot never reads this file.

`record_realized` is called from alpaca_paper._notify_closed when a held position disappears.
"""
import json
import logging
import os
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

REALIZED_FILE = Path(os.environ.get(
    "TONY_REALIZED_FILE",
    str(Path(__file__).parent.parent.parent / "workspace" / "tony-realized.json"),
))


def infer_reason(exit_price, target, stop) -> str:
    """Best-effort exit reason from the fill vs the prior protective levels."""
    if exit_price is None:
        return "unknown"
    try:
        ep = float(exit_price)
    except (TypeError, ValueError):
        return "unknown"
    t = float(target) if target not in (None, "") else None
    s = float(stop) if stop not in (None, "") else None
    if t is not None and ep >= t:
        return "target"
    if s is not None and ep <= s:
        return "stop"
    if t is not None or s is not None:
        return "close"
    return "unknown"


def _load() -> list:
    try:
        data = json.loads(REALIZED_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def record_realized(symbol, qty, entry, exit_price, target=None, stop=None) -> dict | None:
    """Append one realized-trade record. Fail-soft: returns None and never raises on bad input."""
    try:
        q = float(qty)
        en = float(entry)
        ex = float(exit_price)
    except (TypeError, ValueError):
        return None
    realized_pl = round((ex - en) * q, 2)
    pct = round((ex - en) / en * 100, 2) if en else 0.0
    row = {
        "symbol": symbol, "qty": q, "entry": round(en, 4), "exit": round(ex, 4),
        "realized_pl": realized_pl, "pct": pct,
        "reason": infer_reason(ex, target, stop), "date": str(date.today()),
    }
    rows = _load()
    rows.append(row)
    try:
        REALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
        REALIZED_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.warning("realized ledger write failed: %s", exc)
    return row


def _agg(rows: list) -> dict:
    wins = sum(1 for r in rows if float(r.get("realized_pl", 0) or 0) > 0)
    losses = sum(1 for r in rows if float(r.get("realized_pl", 0) or 0) < 0)
    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r.get("reason", "unknown")] = by_reason.get(r.get("reason", "unknown"), 0) + 1
    return {
        "count": len(rows), "wins": wins, "losses": losses,
        "realized_pl": round(sum(float(r.get("realized_pl", 0) or 0) for r in rows), 2),
        "by_reason": by_reason,
    }


def summary() -> dict:
    """today + all-time realized P/L, win/loss counts, by-exit-reason."""
    rows = _load()
    today = str(date.today())
    return {"today": _agg([r for r in rows if r.get("date") == today]),
            "all_time": _agg(rows)}
