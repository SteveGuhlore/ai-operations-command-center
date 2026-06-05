import httpx

from runner.tools import stock_data as sd


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_get(rec=None, earn=None, boom=False):
    def _get(url, params=None, **kwargs):
        if boom:
            raise httpx.ConnectError("down")
        if "recommendation" in url:
            return _Resp(rec if rec is not None else [])
        if "calendar/earnings" in url:
            return _Resp(earn if earn is not None else {"earningsCalendar": []})
        return _Resp({})
    return _get


def test_no_key_is_noop(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert sd._finnhub_enrich("AAA") == {}


def test_enrich_trend_and_earnings(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    rec = [
        {"period": "2026-06-01", "strongBuy": 14, "buy": 24, "hold": 15, "sell": 2, "strongSell": 0},
        {"period": "2026-05-01", "strongBuy": 10, "buy": 20, "hold": 18, "sell": 3, "strongSell": 1},
    ]
    earn = {"earningsCalendar": [{"date": "2026-09-01"}, {"date": "2026-07-29"}]}
    monkeypatch.setattr(sd.httpx, "get", _fake_get(rec=rec, earn=earn))
    out = sd._finnhub_enrich("AAA")
    assert out["analyst_trend"]["strongBuy"] == 14          # latest period first
    assert out["analyst_trend"]["period"] == "2026-06-01"
    assert out["finnhub_next_earnings"] == "2026-07-29"     # soonest upcoming


def test_partial_failure_degrades(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "k")
    monkeypatch.setattr(sd.httpx, "get", _fake_get(boom=True))
    assert sd._finnhub_enrich("AAA") == {}                  # never raises
