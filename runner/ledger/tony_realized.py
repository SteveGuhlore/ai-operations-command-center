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
        "reason": infer_reason(ex, target, stop), "date": _trading_day(),
    }
    rows = _load()
    rows.append(row)
    try:
        REALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
        REALIZED_FILE.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.warning("realized ledger write failed: %s", exc)
    return row


def _pl(r) -> float:
    try:
        return float(r.get("realized_pl", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _agg(rows: list) -> dict:
    # `count`/`wins`/`losses` are TRADES — actual position closes (target/stop/close). Trims
    # (partial re-sizes that left the position open) are tracked separately so they never inflate
    # the "trades closed" narrative, but their realized P/L still rolls into `realized_pl` (real $).
    closed = [r for r in rows if r.get("reason") != "trim"]
    trims = [r for r in rows if r.get("reason") == "trim"]
    by_reason: dict[str, int] = {}
    for r in rows:
        by_reason[r.get("reason", "unknown")] = by_reason.get(r.get("reason", "unknown"), 0) + 1
    return {
        "count": len(closed),
        "wins": sum(1 for r in closed if _pl(r) > 0),
        "losses": sum(1 for r in closed if _pl(r) < 0),
        "realized_pl": round(sum(_pl(r) for r in rows), 2),       # total incl. trims (real money)
        "closed_pl": round(sum(_pl(r) for r in closed), 2),       # P/L from actual closes only
        "trims": len(trims),
        "trim_pl": round(sum(_pl(r) for r in trims), 2),
        "by_reason": by_reason,
    }


def _trading_day() -> str:
    from runner.ledger.market_clock import trading_day
    return trading_day()


def summary() -> dict:
    """today + all-time realized P/L, win/loss counts, by-exit-reason."""
    rows = _load()
    today = _trading_day()  # ET — a 9 PM ET wrap must still see the day's exits (UTC has rolled)
    return {"today": _agg([r for r in rows if r.get("date") == today]),
            "all_time": _agg(rows)}


def records(newest_first: bool = True) -> list:
    """All realized rows ordered by date (then symbol). For the paged /record view."""
    rows = sorted(_load(), key=lambda r: (str(r.get("date", "")), str(r.get("symbol", ""))))
    return list(reversed(rows)) if newest_first else rows


def reconcile_from_fills(fills: list) -> list:
    """FIFO-match SELL fills to prior BUY fills per symbol; return one realized row per SELL with a
    real P/L. `fills`: chronological dicts {symbol, side('buy'/'sell'), qty, price, order_id,
    order_type, time, date}. A SELL with no matching prior BUY in the window is skipped (we never
    invent an entry). order_type maps the exit reason: stop->stop, limit/take_profit->target,
    else->close. This is the authoritative path — it captures stop-outs the live diff never saw."""
    from collections import defaultdict, deque
    lots: dict = defaultdict(deque)  # symbol -> deque([qty, price])
    rows: list = []
    for f in sorted(fills, key=lambda x: str(x.get("time", ""))):
        sym = f.get("symbol")
        side = (f.get("side") or "").lower()
        try:
            qty, price = float(f.get("qty")), float(f.get("price"))
        except (TypeError, ValueError):
            continue
        if qty <= 0 or price <= 0 or not sym:
            continue
        if side == "buy":
            lots[sym].append([qty, price])
        elif side == "sell":
            remaining, cost, matched = qty, 0.0, 0.0
            dq = lots[sym]
            while remaining > 1e-9 and dq:
                lot = dq[0]
                take = min(remaining, lot[0])
                cost += take * lot[1]
                matched += take
                lot[0] -= take
                remaining -= take
                if lot[0] <= 1e-9:
                    dq.popleft()
            if matched <= 1e-9:
                continue  # no entry in the window — don't fabricate a P/L
            avg_entry = cost / matched
            ot = (f.get("order_type") or "").lower()
            reason = "stop" if ot == "stop" else ("target" if ot in ("limit", "take_profit") else "close")
            # A sell that leaves shares STILL OPEN is a TRIM (a partial re-size, e.g. the operator
            # trimming a pyramided position), NOT a position close — so it must not inflate the
            # "trades closed" count or the win/loss/exit-reason stats. The realized P/L is still
            # real money and stays in the total; it's just bucketed as `trim`, not a trade.
            if sum(lot[0] for lot in dq) > 1e-9:
                reason = "trim"
            rows.append({
                "symbol": sym, "qty": round(matched, 4), "entry": round(avg_entry, 4),
                "exit": round(price, 4), "realized_pl": round((price - avg_entry) * matched, 2),
                "pct": round((price - avg_entry) / avg_entry * 100, 2) if avg_entry else 0.0,
                "reason": reason, "date": f.get("date"), "exit_order_id": f.get("order_id"),
            })
    return rows


def rebuild_from_fills(fills: list) -> dict:
    """Merge Alpaca-reconciled exits into the ledger. The reconciled rows are AUTHORITATIVE: where
    an exit_order_id exists in both, the reconciled row replaces the stored one (so a re-derivation
    — e.g. relabeling a partial sell as a trim — actually updates history, instead of the stale row
    shadowing it forever). Rows outside the fetch window are preserved; un-id'd legacy rows drop."""
    reconciled = reconcile_from_fills(fills)
    rec_ids = {r.get("exit_order_id") for r in reconciled}
    kept = [r for r in _load() if r.get("exit_order_id") and r.get("exit_order_id") not in rec_ids]
    prior_count = len([r for r in _load() if r.get("exit_order_id")])
    merged = kept + reconciled
    merged.sort(key=lambda r: (str(r.get("date", "")), str(r.get("symbol", ""))))
    try:
        REALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
        REALIZED_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    except OSError as exc:
        _log.warning("realized rebuild write failed: %s", exc)
    return {"records": len(merged), "added": len(merged) - prior_count,
            "realized_pl": round(sum(float(r.get("realized_pl", 0) or 0) for r in merged), 2)}
