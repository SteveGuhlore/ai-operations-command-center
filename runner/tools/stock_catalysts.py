"""get_catalysts — Tony's event-filing layer from primary sources (no API key needed).

The scanner reasons over price; it never reads a filing. This surfaces the hard events a
quant scan misses: SEC 8-K (material events — M&A, guidance, executive change), Form 4
(insider buying/selling), 13D/G (activist/large stakes), and the 10-Q/10-K cadence. Pulled
straight from SEC EDGAR (free, no key). If FINNHUB_API_KEY is set, it also folds in Finnhub's
aggregated insider-transaction sentiment. Read-only; never raises — degrades to a note.
"""
import logging
import os
from datetime import date, timedelta

import httpx

_log = logging.getLogger(__name__)

# SEC requires a descriptive User-Agent with a contact. Low-volume, read-only research use.
_UA = {"User-Agent": "AI-Ops-Command-Center Tony research (stephenbattaglia594@gmail.com)"}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_FINNHUB_INSIDER_URL = "https://finnhub.io/api/v1/stock/insider-transactions"
_TIMEOUT = 12.0

# Forms worth flagging as catalysts, mapped to a plain-English label for Tony.
_FORMS = {
    "8-K": "material event",
    "4": "insider transaction",
    "3": "insider (initial)",
    "5": "insider (annual)",
    "SC 13D": "activist/large stake",
    "SC 13G": "passive large stake",
    "10-Q": "quarterly report",
    "10-K": "annual report",
    "S-1": "registration/offering",
    "424B5": "shelf offering",
}

_cik_cache: dict[str, int] = {}


def _load_cik_map() -> dict[str, int]:
    if _cik_cache:
        return _cik_cache
    try:
        r = httpx.get(_TICKERS_URL, headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        for row in r.json().values():
            _cik_cache[row["ticker"].upper()] = int(row["cik_str"])
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        _log.info("SEC ticker map failed: %s", exc)
    return _cik_cache


def _accession_nodash(acc: str) -> str:
    return acc.replace("-", "")


def _sec_filings(sym: str, days: int, limit: int) -> tuple[list[dict], int | None]:
    cik = _load_cik_map().get(sym)
    if cik is None:
        return [], None
    try:
        r = httpx.get(_SUBMISSIONS_URL.format(cik=cik), headers=_UA, timeout=_TIMEOUT)
        r.raise_for_status()
        recent = r.json().get("filings", {}).get("recent", {})
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("SEC submissions failed for %s: %s", sym, exc)
        return [], cik

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accs = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    out: list[dict] = []
    for i, form in enumerate(forms):
        if form not in _FORMS:
            continue
        fdate = dates[i] if i < len(dates) else ""
        if fdate < cutoff:
            continue
        acc = accs[i] if i < len(accs) else ""
        doc = docs[i] if i < len(docs) else ""
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{_accession_nodash(acc)}/{doc}"
            if acc and doc else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
        )
        out.append({"form": form, "label": _FORMS[form], "date": fdate, "url": url})
        if len(out) >= limit:
            break
    return out, cik


def _finnhub_insider(sym: str, days: int) -> dict | None:
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return None
    today = date.today()
    params = {
        "symbol": sym,
        "from": (today - timedelta(days=max(days, 90))).isoformat(),
        "to": today.isoformat(),
        "token": key,
    }
    try:
        r = httpx.get(_FINNHUB_INSIDER_URL, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json().get("data", [])
    except (httpx.HTTPError, ValueError) as exc:
        _log.info("finnhub insider failed for %s: %s", sym, exc)
        return None
    if not data:
        return None
    bought = sum(t.get("change", 0) for t in data if t.get("change", 0) > 0)
    sold = -sum(t.get("change", 0) for t in data if t.get("change", 0) < 0)
    net = bought - sold
    return {
        "window_days": max(days, 90),
        "net_shares": net,
        "bought_shares": bought,
        "sold_shares": sold,
        "bias": "net buying" if net > 0 else "net selling" if net < 0 else "flat",
        "transactions": len(data),
    }


def get_catalysts(symbol: str, days: int = 30, limit: int = 15) -> dict:
    """Recent SEC filings + insider bias for a symbol. Read-only; safe any time."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"error": "symbol required"}

    filings, cik = _sec_filings(sym, days, limit)
    insider = _finnhub_insider(sym, days)

    out: dict = {"symbol": sym, "cik": cik, "window_days": days,
                 "filings": filings, "filing_count": len(filings)}
    if insider:
        out["insider"] = insider
    if cik is None:
        out["note"] = f"No SEC CIK found for {sym} (ADR/ETF/foreign issuer may not file with EDGAR)."
    elif not filings:
        out["note"] = f"No 8-K/insider/13D filings for {sym} in the last {days} days."
    return out


TOOL_SPEC = {
    "name": "get_catalysts",
    "description": (
        "Pull recent SEC filings (the hard events the scanner never reads) for a symbol: 8-K "
        "(material events — M&A, guidance cuts, exec changes), Form 4 (insider buying/selling), "
        "13D/13G (activist or large stakes), plus the 10-Q/10-K cadence. Each item has its form, "
        "a plain-English label, the filing date, and a direct EDGAR link. If insider data is "
        "available it also returns the net insider buying/selling bias. Use this to catch a "
        "catalyst or a red flag (insider dumping, a surprise 8-K) before you trust a purely "
        "technical pick. Example: get_catalysts(symbol='GTLB', days=30)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol, e.g. 'GTLB'"},
            "days": {"type": "integer", "description": "Look-back window in days (default 30)."},
            "limit": {"type": "integer", "description": "Max filings to return (default 15)."},
        },
        "required": ["symbol"],
    },
}
