"""equity_history — time-series of Tony vs bot equity for the normalized head-to-head curve.

The two paper accounts have unequal capital (Tony $1M, bot $100k), so the dashboard compares
them on %-return: each series is indexed to 100 at its first recorded snapshot. Tony's equity
comes straight from his Alpaca account; the bot doesn't expose equity, so we mark its open
positions to market ($100k start + realized + unrealized). Both degrade to None on any error so
a missing side never breaks the snapshot. See docs/CONTRACTS/execution-parity.md.
"""
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)

HISTORY_FILE = Path(os.environ.get(
    "TONY_EQUITY_HISTORY",
    str(Path(__file__).parent.parent.parent / "workspace" / "equity-history.json")))
BOT_API = os.environ.get("BOT_API_BASE", "http://127.0.0.1:8001")
BOT_START_CAPITAL = float(os.environ.get("BOT_START_CAPITAL", "100000"))
TONY_START_CAPITAL = float(os.environ.get("TONY_START_CAPITAL", "1000000"))
MAX_POINTS = 5000


def _load() -> list:
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def append_point(points: list, ts: str, tony, bot, *, max_points: int = MAX_POINTS) -> list:
    """Pure: append a snapshot (skipping a fully-empty one), capped to the most recent max_points."""
    if tony is None and bot is None:
        return points
    return (points + [{"ts": ts, "tony": tony, "bot": bot}])[-max_points:]


def indexed_curve(points: list, tony_base: float = TONY_START_CAPITAL,
                  bot_base: float = BOT_START_CAPITAL) -> dict:
    """Pure: index each series to 100 at its STARTING CAPITAL (Tony $1M, bot $100k) so the curve
    shows total %-return since inception. Indexing to start capital (not the first snapshot) means
    the real head-to-head difference is visible immediately and stays put through the close —
    equity only moves when the market is open, so the lines hold their gap overnight."""
    out = []
    for p in points:
        out.append({
            "ts": p.get("ts"),
            "tony": round(p["tony"] / tony_base * 100, 3) if (tony_base and p.get("tony") is not None) else None,
            "bot": round(p["bot"] / bot_base * 100, 3) if (bot_base and p.get("bot") is not None) else None,
        })
    last = points[-1] if points else {}
    return {
        "points": out,
        "tony_return_pct": round((last["tony"] / tony_base - 1) * 100, 2) if (tony_base and last.get("tony") is not None) else None,
        "bot_return_pct": round((last["bot"] / bot_base - 1) * 100, 2) if (bot_base and last.get("bot") is not None) else None,
    }


def _latest_prices(symbols: list) -> dict:
    if not symbols:
        return {}
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest
        key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
        if not (key and secret):
            return {}
        client = StockHistoricalDataClient(key, secret)
        res = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        return {s: float(res[s].price) for s in res}
    except Exception as exc:
        _log.info("equity_history latest_prices: %s", exc)
        return {}


def tony_equity():
    try:
        from runner.ledger.alpaca_paper import account_record
        rec = account_record()
        return float(rec["equity"]) if rec.get("status") == "ok" else None
    except Exception as exc:
        _log.info("tony_equity: %s", exc)
        return None


def bot_equity():
    """Mark-to-market the bot's book: start capital + realized + unrealized (live prices)."""
    try:
        with urllib.request.urlopen(f"{BOT_API}/api/paper/positions", timeout=8) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        _log.info("bot_equity fetch: %s", exc)
        return None
    opens = data.get("open") or []
    realized = float((data.get("summary") or {}).get("realized_pl", 0) or 0)
    prices = _latest_prices([o["symbol"] for o in opens])
    unrealized = 0.0
    for o in opens:
        px, entry = prices.get(o.get("symbol")), o.get("entry_price")
        if px and entry:
            unrealized += float(o.get("qty", 0)) * (px - float(entry))
    return BOT_START_CAPITAL + realized + unrealized


def snapshot() -> dict:
    """Capture one {tony, bot} equity point. Degrades to None sides on error, never raises."""
    points = append_point(_load(), datetime.now(timezone.utc).isoformat(), tony_equity(), bot_equity())
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(points), encoding="utf-8")
    except OSError as exc:
        _log.warning("equity snapshot write failed: %s", exc)
    return {"points": len(points)}


def curve() -> dict:
    """Normalized head-to-head curve for the dashboard."""
    return indexed_curve(_load())
