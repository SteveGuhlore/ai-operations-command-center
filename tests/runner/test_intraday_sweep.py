"""Flag-gated continuous intraday deep-dive sweep (scanner universe + Tony's ideas)."""
import runner.main as m
from runner.bridge import tony_bridge as tb


def _patch(monkeypatch, closed):
    calls = []
    monkeypatch.setattr(tb, "_fanout_deepdives", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(tb, "_latest_bridge_md", lambda: ("2026-06-10T1030", "## Tier 1\n### [[AAA]]"))
    monkeypatch.setattr(m, "_is_market_closed", lambda: closed)
    return calls


def test_sweep_off_by_default(monkeypatch):
    calls = _patch(monkeypatch, closed=False)
    monkeypatch.delenv("TONY_INTRADAY_SWEEP", raising=False)
    m._maybe_intraday_sweep()
    assert calls == []  # inert until explicitly enabled


def test_sweep_fires_when_on_and_market_open(monkeypatch):
    calls = _patch(monkeypatch, closed=False)
    monkeypatch.setenv("TONY_INTRADAY_SWEEP", "on")
    m._maybe_intraday_sweep()
    assert calls == [("2026-06-10T1030", "## Tier 1\n### [[AAA]]")]


def test_sweep_skips_when_market_closed(monkeypatch):
    calls = _patch(monkeypatch, closed=True)
    monkeypatch.setenv("TONY_INTRADAY_SWEEP", "on")
    m._maybe_intraday_sweep()
    assert calls == []  # off-market is the research wave's job, not the sweep
