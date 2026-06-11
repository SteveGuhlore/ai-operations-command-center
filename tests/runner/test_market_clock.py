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


def test_trading_day_is_eastern_not_utc(monkeypatch):
    """8 PM ET = midnight UTC: trading_day() must stay on the ET day, not roll to tomorrow."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from runner.ledger import market_clock as mc
    # 2026-06-11 21:00 ET (= 2026-06-12 01:00 UTC) -> ET day is still the 11th
    et = datetime(2026, 6, 11, 21, 0, tzinfo=ZoneInfo("America/New_York"))
    assert mc.trading_day(et) == "2026-06-11"
    # passing the equivalent UTC-aware instant resolves to the same ET day
    assert mc.trading_day(et.astimezone(ZoneInfo("UTC"))) == "2026-06-11"


def test_daily_gates_stable_across_utc_evening(monkeypatch, tmp_path):
    """preopen_done_today must not flip to False at 8 PM ET just because UTC rolled over."""
    from runner.scheduler import daily_jobs as dj
    monkeypatch.setattr(dj, "STATE_FILE", tmp_path / "sched.json")
    monkeypatch.setattr(dj, "trading_day", lambda: "2026-06-11")
    dj.mark_preopen_ran()
    assert dj.preopen_done_today() is True   # same ET day -> still done
    monkeypatch.setattr(dj, "trading_day", lambda: "2026-06-12")
    assert dj.preopen_done_today() is False  # next ET day -> due again
