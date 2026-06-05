import httpx

from runner.tools import stock_news as sn


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_get(alpaca=None, finnhub=None, boom=False):
    def _get(url, **kwargs):
        if boom:
            raise httpx.ConnectError("network down")
        if "alpaca" in url:
            return _Resp({"news": alpaca or []})
        return _Resp(finnhub or [])
    return _get


def test_symbol_required():
    assert "error" in sn.get_stock_news("")


def test_alpaca_path_parses_and_sorts(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    alpaca = [
        {"headline": "Older", "created_at": "2026-06-01T10:00:00Z", "symbols": ["AAA"], "source": "benzinga"},
        {"headline": "Newer", "created_at": "2026-06-04T10:00:00Z", "symbols": ["AAA"], "source": "benzinga"},
    ]
    monkeypatch.setattr(sn.httpx, "get", _fake_get(alpaca=alpaca))
    r = sn.get_stock_news("aaa", limit=10)
    assert r["count"] == 2
    assert r["articles"][0]["headline"] == "Newer"   # newest first
    assert r["providers"] == ["alpaca"]


def test_merges_and_dedupes_across_providers(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.setenv("FINNHUB_API_KEY", "f")
    alpaca = [{"headline": "Shared Story", "created_at": "2026-06-04T10:00:00Z", "symbols": ["AAA"]}]
    finnhub = [
        {"headline": "Shared Story", "datetime": 1780000000, "source": "reuters"},
        {"headline": "Finnhub Only", "datetime": 1780000500, "source": "reuters"},
    ]
    monkeypatch.setattr(sn.httpx, "get", _fake_get(alpaca=alpaca, finnhub=finnhub))
    r = sn.get_stock_news("AAA", limit=10)
    headlines = [a["headline"] for a in r["articles"]]
    assert headlines.count("Shared Story") == 1     # de-duped
    assert "Finnhub Only" in headlines


def test_no_keys_returns_note(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    r = sn.get_stock_news("AAA")
    assert r["count"] == 0
    assert "note" in r


def test_network_error_degrades_gracefully(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(sn.httpx, "get", _fake_get(boom=True))
    r = sn.get_stock_news("AAA")
    assert r["count"] == 0          # never raises
    assert "note" in r


def test_limit_truncates(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    alpaca = [
        {"headline": f"H{i}", "created_at": f"2026-06-0{i}T10:00:00Z", "symbols": ["AAA"]}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(sn.httpx, "get", _fake_get(alpaca=alpaca))
    r = sn.get_stock_news("AAA", limit=2)
    assert r["count"] == 2
