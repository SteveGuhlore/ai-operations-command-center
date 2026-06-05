from datetime import date, timedelta

import httpx

from runner.tools import stock_catalysts as sc


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _recent(days_ago):
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _fake_get(tickers=None, submissions=None, insider=None, boom_on=None):
    def _get(url, **kwargs):
        if boom_on and boom_on in url:
            raise httpx.ConnectError("down")
        if "company_tickers" in url:
            return _Resp(tickers or {})
        if "submissions" in url:
            return _Resp(submissions or {})
        if "insider-transactions" in url:
            return _Resp(insider or {"data": []})
        return _Resp({})
    return _get


def setup_function():
    sc._cik_cache.clear()


def test_symbol_required():
    assert "error" in sc.get_catalysts("")


def test_filters_forms_and_window(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    tickers = {"0": {"cik_str": 320193, "ticker": "AAA"}}
    submissions = {"filings": {"recent": {
        "form": ["8-K", "4", "DEF 14A", "10-Q"],          # DEF 14A not in _FORMS -> dropped
        "filingDate": [_recent(2), _recent(5), _recent(1), _recent(400)],  # 10-Q too old -> dropped
        "accessionNumber": ["0001-23-000001", "0001-23-000002", "x", "y"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"],
    }}}
    monkeypatch.setattr(sc.httpx, "get", _fake_get(tickers=tickers, submissions=submissions))
    r = sc.get_catalysts("aaa", days=30)
    forms = [f["form"] for f in r["filings"]]
    assert forms == ["8-K", "4"]                          # DEF 14A filtered, 10-Q out of window
    assert r["filings"][0]["url"].endswith("/000123000001/a.htm")
    assert r["filings"][0]["label"] == "material event"
    assert r["cik"] == 320193


def test_unknown_ticker_notes_no_cik(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(sc.httpx, "get", _fake_get(tickers={"0": {"cik_str": 1, "ticker": "AAA"}}))
    r = sc.get_catalysts("ZZZZ")
    assert r["cik"] is None
    assert "note" in r


def test_insider_bias_when_key_present(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "f")
    tickers = {"0": {"cik_str": 1, "ticker": "AAA"}}
    submissions = {"filings": {"recent": {"form": [], "filingDate": [], "accessionNumber": [], "primaryDocument": []}}}
    insider = {"data": [{"change": 1000}, {"change": -2500}, {"change": 500}]}  # net -1000
    monkeypatch.setattr(sc.httpx, "get", _fake_get(tickers=tickers, submissions=submissions, insider=insider))
    r = sc.get_catalysts("AAA")
    assert r["insider"]["bias"] == "net selling"
    assert r["insider"]["net_shares"] == -1000
    assert r["insider"]["transactions"] == 3


def test_network_error_degrades(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(sc.httpx, "get", _fake_get(boom_on="company_tickers"))
    r = sc.get_catalysts("AAA")
    assert r["cik"] is None          # never raises
    assert r["filing_count"] == 0
