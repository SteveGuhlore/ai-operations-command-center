import httpx

from runner.tools import market_regime as mr


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_fred(values):
    """values: {series_id: "4.49" | "."} -> mock one observation per series."""
    def _get(url, params=None, **kwargs):
        sid = (params or {}).get("series_id")
        return _Resp({"observations": [{"date": "2026-06-04", "value": values.get(sid, ".")}]})
    return _get


def test_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert mr._fred_yields() is None


def test_yields_and_normal_curve(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(mr.httpx, "get", _fake_fred({"DGS10": "4.49", "DGS2": "4.08"}))
    y = mr._fred_yields()
    assert y["dgs10"] == 4.49 and y["dgs2"] == 4.08
    assert y["spread_2s10s"] == 0.41
    assert y["curve"] == "normal"


def test_inverted_curve_sets_macro_flag(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(mr.httpx, "get", _fake_fred({"DGS10": "3.80", "DGS2": "4.50"}))
    monkeypatch.setattr(mr, "_fetch", lambda: {"vix": 14.0, "spy_above_sma50": True, "sector_rs": {}})
    r = mr.get_market_regime()
    assert r["rates"]["curve"] == "inverted"
    assert r["macro_flags"] == ["yield_curve_inverted"]


def test_missing_value_degrades(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "k")
    monkeypatch.setattr(mr.httpx, "get", _fake_fred({"DGS10": ".", "DGS2": "."}))
    assert mr._fred_yields() is None


def test_regime_has_no_rates_without_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setattr(mr, "_fetch", lambda: {"vix": 14.0, "spy_above_sma50": True, "sector_rs": {}})
    r = mr.get_market_regime()
    assert "rates" not in r
