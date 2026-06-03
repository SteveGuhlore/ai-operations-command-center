from runner.tools import stock_technicals as st


def test_indicators_from_synthetic_closes(monkeypatch):
    closes = [10 + (i % 5) for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1000 + i for i in range(60)]
    monkeypatch.setattr(st, "_fetch_ohlcv", lambda sym, days: {
        "close": closes, "high": highs, "low": lows, "volume": vols})
    r = st.get_price_history("TEST", days=60)
    assert r["symbol"] == "TEST"
    assert 0 <= r["rsi14"] <= 100
    assert r["sma20"] is not None and r["sma50"] is not None
    assert r["atr14"] > 0
    assert r["volume_trend"] in ("rising", "falling", "flat")


def test_volume_trend_rising(monkeypatch):
    closes = [10.0] * 60
    vols = [1000.0] * 55 + [5000.0] * 5
    monkeypatch.setattr(st, "_fetch_ohlcv", lambda sym, days: {
        "close": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes], "volume": vols})
    assert st.get_price_history("TEST")["volume_trend"] == "rising"


def test_blank_symbol_errors():
    assert "error" in st.get_price_history("")
