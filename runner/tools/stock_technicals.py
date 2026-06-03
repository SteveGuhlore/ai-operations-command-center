"""get_price_history — Tony's own technical read (yfinance OHLCV → RSI/SMA/ATR).

Lets the second layer verify the scanner's setup on its own indicators instead of
trusting the bot's chart. Pure math is split from the network fetch so it unit-tests
without hitting Yahoo.
"""
import logging

_log = logging.getLogger(__name__)


def _fetch_ohlcv(symbol: str, days: int) -> dict:
    import yfinance as yf
    period = "1y" if days > 180 else "6mo" if days > 90 else "3mo"
    h = yf.Ticker(symbol).history(period=period)
    if h is None or h.empty:
        raise ValueError("no history")
    tail = h.tail(days)
    return {
        "close": [float(x) for x in tail["Close"]],
        "high": [float(x) for x in tail["High"]],
        "low": [float(x) for x in tail["Low"]],
        "volume": [float(x) for x in tail["Volume"]],
    }


def _sma(vals, n):
    return round(sum(vals[-n:]) / n, 2) if len(vals) >= n else None


def _rsi(closes, n=14):
    if len(closes) <= n:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-n:]) / n
    al = sum(losses[-n:]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return round(100 - 100 / (1 + rs), 1)


def _atr(high, low, close, n=14):
    if len(close) <= n:
        return None
    trs = []
    for i in range(1, len(close)):
        trs.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return round(sum(trs[-n:]) / n, 2)


def _vol_trend(vols):
    if len(vols) < 20:
        return "flat"
    recent = sum(vols[-5:]) / 5
    base = sum(vols[-20:]) / 20
    if recent > base * 1.15:
        return "rising"
    if recent < base * 0.85:
        return "falling"
    return "flat"


def get_price_history(symbol: str, days: int = 60) -> dict:
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}
    try:
        o = _fetch_ohlcv(sym, days)
    except ImportError:
        return {"error": "yfinance not installed"}
    except Exception as exc:
        return {"symbol": sym, "error": f"history unavailable: {exc}"}

    c, h, l = o["close"], o["high"], o["low"]
    last = c[-1]
    hi = max(h)
    sma50 = _sma(c, 50)
    return {
        "symbol": sym,
        "last": round(last, 2),
        "rsi14": _rsi(c),
        "sma20": _sma(c, 20),
        "sma50": sma50,
        "atr14": _atr(h, l, c),
        "pct_from_52w_high": round((last - hi) / hi * 100, 1) if hi else None,
        "pct_above_sma50": round((last - sma50) / sma50 * 100, 1) if sma50 else None,
        "volume_trend": _vol_trend(o["volume"]),
    }


TOOL_SPEC = {
    "name": "get_price_history",
    "description": (
        "Your OWN technical read on a ticker (yfinance OHLC). Returns last, RSI(14), "
        "SMA20/SMA50, ATR(14), pct_from_52w_high, pct_above_sma50, volume_trend. Use it to "
        "verify the scanner's setup on your own indicators — confirm a breakout with RSI + "
        "volume_trend, or size a stop off ATR. Example: get_price_history(symbol='GTLB')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "days": {"type": "integer", "description": "lookback window, default 60"},
        },
        "required": ["symbol"],
    },
}
