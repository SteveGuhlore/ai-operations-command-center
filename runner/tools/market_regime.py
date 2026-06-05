"""get_market_regime — macro context as data, not prose.

Reads VIX + SPY trend + sector-ETF relative strength (yfinance) and classifies the tape
risk_on / neutral / risk_off, so Tony can gate conviction (e.g. downgrade one tier in
risk_off). The scanner's regime is equity-only; this also layers the rates picture (10Y/2Y
Treasury yields + the 2s10s curve) from FRED when FRED_API_KEY is set — an inverted curve is
a macro risk flag a price-based scanner never sees. Network fetches are isolated for testing.
"""
import logging
import os

import httpx

_log = logging.getLogger(__name__)

_SECTORS = {"XLK": "Tech", "XLE": "Energy", "XLF": "Financials", "XLV": "Health",
            "XLI": "Industrials", "XLY": "Discretionary", "XLP": "Staples", "XLU": "Utilities"}

_FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
_FRED_TIMEOUT = 12.0


def _fred_latest(series_id: str, key: str) -> float | None:
    params = {"series_id": series_id, "api_key": key, "file_type": "json",
              "sort_order": "desc", "limit": 1}
    try:
        r = httpx.get(_FRED_URL, params=params, timeout=_FRED_TIMEOUT)
        r.raise_for_status()
        obs = r.json().get("observations", [])
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("FRED %s failed: %s", series_id, exc)
        return None
    if not obs:
        return None
    val = obs[0].get("value")
    try:
        return float(val)        # FRED uses "." for missing readings -> ValueError -> None
    except (TypeError, ValueError):
        return None


def _fred_yields() -> dict | None:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    dgs10 = _fred_latest("DGS10", key)
    dgs2 = _fred_latest("DGS2", key)
    if dgs10 is None and dgs2 is None:
        return None
    out: dict = {"dgs10": dgs10, "dgs2": dgs2}
    if dgs10 is not None and dgs2 is not None:
        spread = round(dgs10 - dgs2, 2)
        out["spread_2s10s"] = spread
        out["curve"] = "inverted" if spread < 0 else "flat" if spread < 0.2 else "normal"
    return out


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
    out = {
        "regime": regime,
        "vix": round(vix, 2),
        "spy_above_sma50": spy_ok,
        "leaders": leaders,
        "laggards": laggards,
    }
    rates = _fred_yields()
    if rates:
        out["rates"] = rates
        if rates.get("curve") == "inverted":
            out["macro_flags"] = ["yield_curve_inverted"]
    return out


TOOL_SPEC = {
    "name": "get_market_regime",
    "description": (
        "The macro tape as data: VIX level, whether SPY is above its 50-day, and sector-ETF "
        "relative strength (leaders/laggards). Returns regime = risk_on | neutral | risk_off, "
        "plus (when FRED is configured) a `rates` block — 10Y/2Y Treasury yields and the 2s10s "
        "curve (normal/flat/inverted) — and `macro_flags` like yield_curve_inverted. "
        "Check it once per brief — in risk_off or an inverted curve, downgrade conviction one "
        "tier and favor leading sectors; in risk_on you can lean in. Example: get_market_regime()"
    ),
    "input_schema": {"type": "object", "properties": {}},
}
