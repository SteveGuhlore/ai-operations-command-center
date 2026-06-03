"""get_stock_data — Tony Stocks' independent financial-data tool.

Gives the second-layer analyst real fundamentals + a live quote (yfinance, free,
no API key) so his verdict rests on data, not just news snippets and the scanner's
stale close. Degrades field-by-field: if Yahoo rate-limits the heavy `.info`, the
fast quote still returns so Tony at least has a current price.
"""
import logging
from datetime import datetime, timezone

_log = logging.getLogger(__name__)


def _round(v, n: int = 2):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def _pct(v):
    try:
        return round(float(v) * 100, 2)
    except (TypeError, ValueError):
        return None


def _fmt_ts(ts) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except (ValueError, OSError, TypeError):
        return None


def get_stock_data(symbol: str) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed — run: pip install yfinance"}

    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}

    out: dict = {"symbol": sym}
    try:
        t = yf.Ticker(sym)

        # Live quote first — most reliable, rarely rate-limited.
        fi = t.fast_info
        last = float(fi.last_price)
        prev = float(fi.previous_close) if fi.previous_close else None
        out["price"] = round(last, 2)
        out["prev_close"] = round(prev, 2) if prev else None
        out["day_change_pct"] = round((last - prev) / prev * 100, 2) if prev else None
        out["year_high"] = round(float(fi.year_high), 2) if fi.year_high else None
        out["year_low"] = round(float(fi.year_low), 2) if fi.year_low else None
    except Exception as exc:
        return {"symbol": sym, "error": f"quote unavailable: {exc}"}

    # Fundamentals — best-effort; never fail the whole call on Yahoo flakiness.
    try:
        info = t.info or {}
        out.update({
            "name": info.get("shortName") or info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_trailing": _round(info.get("trailingPE")),
            "pe_forward": _round(info.get("forwardPE")),
            "revenue_growth_pct": _pct(info.get("revenueGrowth")),
            "earnings_growth_pct": _pct(info.get("earningsGrowth")),
            "profit_margin_pct": _pct(info.get("profitMargins")),
            "beta": _round(info.get("beta")),
            "analyst_target_mean": _round(info.get("targetMeanPrice")),
            "analyst_rating": info.get("recommendationKey"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
            "next_earnings_date": _fmt_ts(info.get("earningsTimestamp")),
            "short_pct_float": _pct(info.get("shortPercentOfFloat")),
        })
        if out.get("analyst_target_mean") and out.get("price"):
            out["analyst_upside_pct"] = round(
                (out["analyst_target_mean"] - out["price"]) / out["price"] * 100, 1
            )
    except Exception as exc:
        out["fundamentals_note"] = f"fundamentals partial (Yahoo throttled): {exc}"

    return out


TOOL_SPEC = {
    "name": "get_stock_data",
    "description": (
        "Pull live price + fundamentals for a ticker (real market data, not the scanner's "
        "stale close). Returns: price, day_change_pct, 52-week high/low, market_cap, "
        "pe_trailing/pe_forward, revenue_growth_pct, earnings_growth_pct, profit_margin_pct, "
        "beta, analyst_target_mean + analyst_upside_pct + analyst_rating, next_earnings_date, "
        "short_pct_float. Call this for every ticker you give a verdict on — it is your "
        "independent check on the scanner's numbers and your fundamentals source. "
        "Example: get_stock_data(symbol='GTLB')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. 'GTLB'"},
        },
        "required": ["symbol"],
    },
}
