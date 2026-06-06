import datetime as dt

from runner.ledger import market_clock as mc


def _reset_cache():
    mc._cache["value"] = None
    mc._cache["ts"] = 0.0


def test_env_override_wins(monkeypatch):
    _reset_cache()
    monkeypatch.setenv("TONY_MARKET_SESSION", "open")
    assert mc.market_session() == "open"
    monkeypatch.setenv("TONY_MARKET_SESSION", "CLOSED")
    assert mc.market_session() == "closed"


def test_env_override_ignored_when_garbage(monkeypatch):
    _reset_cache()
    monkeypatch.setenv("TONY_MARKET_SESSION", "banana")
    monkeypatch.setattr(mc, "_alpaca_clock_open", lambda: None)
    # falls through to fail-safe; a Saturday is closed
    monkeypatch.setattr(mc, "_is_rth", lambda now=None: False)
    assert mc.market_session() == "closed"


def test_alpaca_clock_authority(monkeypatch):
    _reset_cache()
    monkeypatch.delenv("TONY_MARKET_SESSION", raising=False)
    monkeypatch.setattr(mc, "_alpaca_clock_open", lambda: True)
    assert mc.market_session() == "open"
    _reset_cache()
    monkeypatch.setattr(mc, "_alpaca_clock_open", lambda: False)
    assert mc.market_session() == "closed"


def test_failsafe_when_no_clock(monkeypatch):
    _reset_cache()
    monkeypatch.delenv("TONY_MARKET_SESSION", raising=False)
    monkeypatch.setattr(mc, "_alpaca_clock_open", lambda: None)
    monkeypatch.setattr(mc, "_is_rth", lambda now=None: True)
    assert mc.market_session() == "open"


def test_cache_avoids_reclocking(monkeypatch):
    _reset_cache()
    monkeypatch.delenv("TONY_MARKET_SESSION", raising=False)
    calls = {"n": 0}

    def _clock():
        calls["n"] += 1
        return True

    monkeypatch.setattr(mc, "_alpaca_clock_open", _clock)
    assert mc.market_session() == "open"
    assert mc.market_session() == "open"
    assert calls["n"] == 1  # second call served from cache


ET = mc._ET


def test_is_rth_weekday_open():
    # Tuesday 2026-06-09, 10:00 ET -> open
    now = dt.datetime(2026, 6, 9, 10, 0, tzinfo=ET)
    assert mc._is_rth(now) is True


def test_is_rth_before_open_and_after_close():
    assert mc._is_rth(dt.datetime(2026, 6, 9, 9, 29, tzinfo=ET)) is False
    assert mc._is_rth(dt.datetime(2026, 6, 9, 16, 0, tzinfo=ET)) is False
    assert mc._is_rth(dt.datetime(2026, 6, 9, 15, 59, tzinfo=ET)) is True


def test_is_rth_weekend():
    # Saturday 2026-06-06
    assert mc._is_rth(dt.datetime(2026, 6, 6, 12, 0, tzinfo=ET)) is False
    # Sunday 2026-06-07
    assert mc._is_rth(dt.datetime(2026, 6, 7, 12, 0, tzinfo=ET)) is False


def test_is_rth_holiday_juneteenth():
    # Friday 2026-06-19 is Juneteenth — a weekday but a market holiday
    assert mc._is_rth(dt.datetime(2026, 6, 19, 12, 0, tzinfo=ET)) is False
