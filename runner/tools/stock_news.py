"""get_stock_news — Tony's qualitative event layer (the scanner is blind to this).

The scanner scores price/volume/technicals; it does not READ the news. This tool gives
Tony timestamped, ticker-tagged headlines so his second-layer pass can reason over
catalysts the quant pipeline can't see. Sources, best-first with graceful degradation:
  - Alpaca News (uses the Alpaca keys already in env — read-only market data, account-agnostic);
  - Finnhub company-news (only if FINNHUB_API_KEY is set).
Returns merged, de-duplicated, newest-first. Never raises: missing keys / network errors
come back as a structured note so Tony's cycle never breaks on it.
"""
import logging
import os
from datetime import date, datetime, timedelta, timezone

import httpx

_log = logging.getLogger(__name__)

_ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
_FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_TIMEOUT = 12.0


def _iso(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).isoformat()
    except (ValueError, TypeError):
        return ts


def _from_unix(ts) -> str | None:
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError, TypeError):
        return None


def _alpaca_news(sym: str, limit: int) -> list[dict]:
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        return []
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {"symbols": sym, "limit": min(limit, 50), "sort": "desc"}
    try:
        r = httpx.get(_ALPACA_NEWS_URL, headers=headers, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        items = r.json().get("news", [])
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("alpaca news failed for %s: %s", sym, exc)
        return []
    return [
        {
            "headline": a.get("headline"),
            "summary": (a.get("summary") or "")[:400],
            "source": a.get("source") or "alpaca",
            "url": a.get("url"),
            "published": _iso(a.get("created_at")),
            "symbols": a.get("symbols") or [sym],
            "provider": "alpaca",
        }
        for a in items if a.get("headline")
    ]


def _finnhub_news(sym: str, days: int) -> list[dict]:
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return []
    today = date.today()
    params = {
        "symbol": sym,
        "from": (today - timedelta(days=days)).isoformat(),
        "to": today.isoformat(),
        "token": key,
    }
    try:
        r = httpx.get(_FINNHUB_NEWS_URL, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        items = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("finnhub news failed for %s: %s", sym, exc)
        return []
    if not isinstance(items, list):
        return []
    return [
        {
            "headline": a.get("headline"),
            "summary": (a.get("summary") or "")[:400],
            "source": a.get("source") or "finnhub",
            "url": a.get("url"),
            "published": _from_unix(a.get("datetime")),
            "symbols": [sym],
            "provider": "finnhub",
        }
        for a in items if a.get("headline")
    ]


def get_stock_news(symbol: str, limit: int = 10, days: int = 14) -> dict:
    """Recent, ticker-tagged, timestamped news for a symbol. Read-only; safe any time."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}

    articles = _alpaca_news(sym, limit) + _finnhub_news(sym, days)

    # De-dupe by normalized headline, keep the newest, then sort newest-first.
    seen: dict[str, dict] = {}
    for a in articles:
        key = (a["headline"] or "").strip().lower()
        if key and (key not in seen or (a["published"] or "") > (seen[key]["published"] or "")):
            seen[key] = a
    merged = sorted(seen.values(), key=lambda a: a["published"] or "", reverse=True)[:limit]

    providers = sorted({a["provider"] for a in merged})
    out = {"symbol": sym, "count": len(merged), "articles": merged, "providers": providers}
    if not merged:
        out["note"] = (
            "No news returned. Check ALPACA_API_KEY/ALPACA_SECRET_KEY (Alpaca news) "
            "or set FINNHUB_API_KEY for company-news — or there is simply no recent coverage."
        )
    return out


TOOL_SPEC = {
    "name": "get_stock_news",
    "description": (
        "Pull recent, timestamped, ticker-tagged NEWS for a symbol — your event layer. The "
        "scanner scores price/technicals but cannot read headlines; this is where your second "
        "pass adds value. Returns up to `limit` articles (headline, summary, source, url, "
        "published time), newest first, merged from Alpaca News (+ Finnhub if configured). "
        "Read the catalysts and news risk before you set a verdict — an earnings beat, a "
        "downgrade, an FDA/legal headline can flip the scanner's purely-technical pick. "
        "Example: get_stock_news(symbol='GTLB', limit=8, days=10)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. 'GTLB'"},
            "limit": {"type": "integer", "description": "Max articles to return (default 10)."},
            "days": {"type": "integer", "description": "Look-back window in days for Finnhub (default 14)."},
        },
        "required": ["symbol"],
    },
}
