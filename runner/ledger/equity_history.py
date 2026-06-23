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

from runner.ledger._jsonio import atomic_write_json, load_list

_log = logging.getLogger(__name__)

# Honor both env names with one precedence (this writer historically used
# TONY_EQUITY_HISTORY, the drawdown breaker reader used TONY_EQUITY_HISTORY_FILE) so
# setting either var can never split writer and reader onto different files.
HISTORY_FILE = Path(
    os.environ.get("TONY_EQUITY_HISTORY")
    or os.environ.get("TONY_EQUITY_HISTORY_FILE")
    or str(Path(__file__).parent.parent.parent / "workspace" / "equity-history.json")
)
BOT_API = os.environ.get("BOT_API_BASE", "http://127.0.0.1:8001")
BOT_START_CAPITAL = float(os.environ.get("BOT_START_CAPITAL", "100000"))
TONY_START_CAPITAL = float(os.environ.get("TONY_START_CAPITAL", "1000000"))
MAX_POINTS = 5000


def _load() -> list:
    return load_list(HISTORY_FILE)


def append_point(
    points: list, ts: str, tony, bot, *, max_points: int = MAX_POINTS
) -> list:
    """Pure: append a snapshot (skipping a fully-empty one), capped to the most recent max_points."""
    if tony is None and bot is None:
        return points
    return (points + [{"ts": ts, "tony": tony, "bot": bot}])[-max_points:]


def indexed_curve(
    points: list,
    tony_base: float = TONY_START_CAPITAL,
    bot_base: float = BOT_START_CAPITAL,
) -> dict:
    """Pure: index each series to 100 at its STARTING CAPITAL (Tony $1M, bot $100k) so the curve
    shows total %-return since inception. Indexing to start capital (not the first snapshot) means
    the real head-to-head difference is visible immediately and stays put through the close —
    equity only moves when the market is open, so the lines hold their gap overnight."""
    out = []
    for p in points:
        out.append(
            {
                "ts": p.get("ts"),
                "tony": round(p["tony"] / tony_base * 100, 3)
                if (tony_base and p.get("tony") is not None)
                else None,
                "bot": round(p["bot"] / bot_base * 100, 3)
                if (bot_base and p.get("bot") is not None)
                else None,
            }
        )
    last = points[-1] if points else {}
    return {
        "points": out,
        "tony_return_pct": round((last["tony"] / tony_base - 1) * 100, 2)
        if (tony_base and last.get("tony") is not None)
        else None,
        "bot_return_pct": round((last["bot"] / bot_base - 1) * 100, 2)
        if (bot_base and last.get("bot") is not None)
        else None,
    }


def _latest_prices(symbols: list) -> dict:
    if not symbols:
        return {}
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest

        key, secret = (
            os.environ.get("ALPACA_API_KEY"),
            os.environ.get("ALPACA_SECRET_KEY"),
        )
        if not (key and secret):
            return {}
        client = StockHistoricalDataClient(key, secret)
        res = client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbols)
        )
        return {s: float(res[s].price) for s in res}
    except Exception as exc:
        _log.info("equity_history latest_prices: %s", exc)
        return {}


def mark_live(acct: dict) -> dict:
    """Re-price an Alpaca account dict to LIVE last-trade prices (mutates in place).

    Alpaca's paper-position `current_price` lags the real market badly (often by several
    percent), so the book and the equity it implies are stale. This recomputes each
    position's current_price / unrealized_pl / unrealized_plpc from a fresh last trade and
    sets equity = cash + sum(qty * live_price). It keeps Tony symmetric with the bot, whose
    equity already marks to live prices. Degrades to the original Alpaca values (priced_live
    False) when the live feed is unavailable, so the book never breaks."""
    positions = acct.get("open_positions") or []
    prices = _latest_prices([p["symbol"] for p in positions if p.get("symbol")])
    if not prices:
        acct["priced_live"] = False
        return acct
    cash = float(acct.get("cash") or 0)
    market_value = 0.0
    for p in positions:
        live = prices.get(p.get("symbol"))
        qty = float(p.get("qty") or 0)
        entry = p.get("avg_entry_price")
        if live is not None:
            p["current_price"] = live
            if entry:
                p["unrealized_pl"] = round(qty * (live - float(entry)), 2)
                p["unrealized_plpc"] = (live - float(entry)) / float(entry)
        px = p.get("current_price")
        market_value += qty * (px if px is not None else 0)
    acct["equity"] = round(cash + market_value, 2)
    acct["priced_live"] = True
    return acct


def tony_equity():
    try:
        from runner.ledger.alpaca_paper import account_record

        rec = account_record()
        if rec.get("status") != "ok":
            return None
        return mark_live(rec).get("equity")
    except Exception as exc:
        _log.info("tony_equity: %s", exc)
        return None


def bot_equity():
    """Mark-to-market the bot's book: start capital + realized + unrealized (live prices)."""
    try:
        with urllib.request.urlopen(
            f"{BOT_API}/api/paper/positions", timeout=8
        ) as resp:
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
    points = append_point(
        _load(), datetime.now(timezone.utc).isoformat(), tony_equity(), bot_equity()
    )
    try:
        atomic_write_json(HISTORY_FILE, points)
    except OSError as exc:
        _log.warning("equity snapshot write failed: %s", exc)
    return {"points": len(points)}


def curve() -> dict:
    """Normalized head-to-head curve for the dashboard."""
    return indexed_curve(_load())


def _bot_equity_at(ts, opens: list, bars_by_sym: dict, start_capital: float) -> float:
    """Pure: reconstruct the bot's mark-to-market equity at time `ts` — start capital plus the
    unrealized P&L of every position already open by then, priced at the latest bar <= ts."""
    unrealized = 0.0
    for o in opens:
        if o.get("opened_at") and o["opened_at"] > ts:
            continue  # not yet held at this point in time
        px = None
        for bts, close in bars_by_sym.get(o["symbol"], []):  # sorted ascending
            if bts <= ts:
                px = close
            else:
                break
        if px is None:
            continue  # no price yet -> treat as just-entered (0 unrealized)
        unrealized += o["qty"] * (px - o["entry_price"])
    return start_capital + unrealized


def _tony_portfolio_history(days: int):
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetPortfolioHistoryRequest

        key, secret = (
            os.environ.get("ALPACA_API_KEY"),
            os.environ.get("ALPACA_SECRET_KEY"),
        )
        if not (key and secret):
            return []
        c = TradingClient(key, secret, paper=True)
        ph = c.get_portfolio_history(
            GetPortfolioHistoryRequest(
                period=f"{days}D", timeframe="1H", intraday_reporting="market_hours"
            )
        )
        # Drop pre-funding / no-data samples (equity 0 or a tiny placeholder) — a real $1M paper
        # account never sits below half its base, so this cleanly removes the leading garbage.
        floor = TONY_START_CAPITAL * 0.5
        out = []
        for ts, eq in zip(ph.timestamp or [], ph.equity or []):
            if eq and eq > floor:
                out.append((datetime.fromtimestamp(ts, tz=timezone.utc), float(eq)))
        return out
    except Exception as exc:
        _log.warning("tony portfolio history: %s", exc)
        return []


def _bot_open_positions() -> list:
    try:
        with urllib.request.urlopen(
            f"{BOT_API}/api/paper/positions", timeout=8
        ) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        _log.info("bot positions fetch: %s", exc)
        return []
    out = []
    for o in data.get("open") or []:
        try:
            oa = o.get("opened_at")
            opened = (
                datetime.fromisoformat(oa.replace("Z", "+00:00"))
                if oa
                else datetime(1970, 1, 1, tzinfo=timezone.utc)
            )
        except ValueError:
            opened = datetime(1970, 1, 1, tzinfo=timezone.utc)
        out.append(
            {
                "symbol": o["symbol"],
                "qty": float(o["qty"]),
                "entry_price": float(o["entry_price"]),
                "opened_at": opened,
            }
        )
    return out


def _historical_bars(symbols: list, days: int) -> dict:
    if not symbols:
        return {}
    try:
        from datetime import timedelta
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        key, secret = (
            os.environ.get("ALPACA_API_KEY"),
            os.environ.get("ALPACA_SECRET_KEY"),
        )
        if not (key and secret):
            return {}
        client = StockHistoricalDataClient(key, secret)
        req = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Hour,
            start=datetime.now(timezone.utc) - timedelta(days=days),
        )
        data = client.get_stock_bars(req).data
        return {
            s: sorted((b.timestamp, float(b.close)) for b in data.get(s, []))
            for s in symbols
        }
    except Exception as exc:
        _log.warning("historical bars: %s", exc)
        return {}


def backfill(days: int = 7) -> dict:
    """Seed the history with REAL intraday equity for both books so the curve has shape before
    the next open — Tony from his Alpaca portfolio history, the bot reconstructed from its open
    positions marked to market on historical bars. Keeps any live points newer than the backfill."""
    tony = _tony_portfolio_history(days)
    if not tony:
        return {"status": "no_tony_history", "points": 0}
    opens = _bot_open_positions()
    bars = _historical_bars(sorted({o["symbol"] for o in opens}), days)
    pts = [
        {
            "ts": ts.isoformat(),
            "tony": eq,
            "bot": round(_bot_equity_at(ts, opens, bars, BOT_START_CAPITAL), 2)
            if opens
            else BOT_START_CAPITAL,
        }
        for ts, eq in tony
    ]
    last_ts = pts[-1]["ts"] if pts else ""
    live_newer = [
        p for p in _load() if str(p.get("ts", "")) > last_ts
    ]  # don't lose live points
    pts = (pts + live_newer)[-MAX_POINTS:]
    try:
        atomic_write_json(HISTORY_FILE, pts)
    except OSError as exc:
        _log.warning("backfill write failed: %s", exc)
    return {"status": "ok", "points": len(pts)}
