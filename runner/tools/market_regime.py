"""get_market_regime — macro context as data, not prose.

Reads VIX + SPY trend + sector-ETF relative strength (yfinance) and classifies the tape
risk_on / neutral / risk_off, so Tony can gate conviction (e.g. downgrade one tier in
risk_off). The network fetch is isolated for unit testing.
"""
import logging

_log = logging.getLogger(__name__)

_SECTORS = {"XLK": "Tech", "XLE": "Energy", "XLF": "Financials", "XLV": "Health",
            "XLI": "Industrials", "XLY": "Discretionary", "XLP": "Staples", "XLU": "Utilities"}


def _fetch() -> dict:
    import yfinance as yf

    vix = float(yf.Ticker("^VIX").fast_info.last_price)

    spy_hist = yf.Ticker("SPY").history(period="3mo")["Close"]
    spy_closes = [float(x) for x in spy_hist]
    spy_last = spy_closes[-1]
    spy_sma50 = sum(spy_closes[-50:]) / min(50, len(spy_closes))

    sector_rs = {}
    for etf in _SECTORS:
        try:
            h = [float(x) for x in yf.Ticker(etf).history(period="1mo")["Close"]]
            if len(h) >= 2:
                sector_rs[etf] = round((h[-1] - h[0]) / h[0] * 100, 2)
        except Exception:
            continue
    return {"vix": vix, "spy_above_sma50": spy_last > spy_sma50, "sector_rs": sector_rs}


def get_market_regime() -> dict:
    try:
        d = _fetch()
    except ImportError:
        return {"error": "yfinance not installed"}
    except Exception as exc:
        return {"error": f"regime unavailable: {exc}"}

    vix = d["vix"]
    spy_ok = d["spy_above_sma50"]
    if vix < 18 and spy_ok:
        regime = "risk_on"
    elif vix > 27 or not spy_ok:
        regime = "risk_off"
    else:
        regime = "neutral"

    rs = d.get("sector_rs", {})
    ranked = sorted(rs.items(), key=lambda kv: -kv[1])
    leaders = [f"{_SECTORS.get(k, k)} ({k})" for k, _ in ranked[:3]]
    laggards = [f"{_SECTORS.get(k, k)} ({k})" for k, _ in ranked[-3:]] if len(ranked) >= 3 else []
    return {
        "regime": regime,
        "vix": round(vix, 2),
        "spy_above_sma50": spy_ok,
        "leaders": leaders,
        "laggards": laggards,
    }


TOOL_SPEC = {
    "name": "get_market_regime",
    "description": (
        "The macro tape as data: VIX level, whether SPY is above its 50-day, and sector-ETF "
        "relative strength (leaders/laggards). Returns regime = risk_on | neutral | risk_off. "
        "Check it once per brief — in risk_off, downgrade conviction one tier and favor "
        "leading sectors; in risk_on you can lean in. Example: get_market_regime()"
    ),
    "input_schema": {"type": "object", "properties": {}},
}
