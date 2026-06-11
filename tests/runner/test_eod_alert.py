"""CC-side missing-EOD-handoff detection: an anomaly signal that the bot's end-of-day bridge
didn't land (today's failure mode — the watch loop stopped at 13:00 and dropped no EOD)."""
import runner.main as m
from runner.bridge import tony_bridge as tb


def test_eod_present_detects_eod_slot(tmp_path, monkeypatch):
    import datetime
    from runner.ledger.market_clock import _ET
    bd = tmp_path / "bridge"; bd.mkdir()
    monkeypatch.setattr(tb, "BRIDGE_MD_DIR", bd)
    now = datetime.datetime(2026, 6, 10, 17, 0, tzinfo=_ET)
    (bd / "2026-06-10.md").write_text("morning")
    (bd / "2026-06-10T1300.md").write_text("intraday")
    assert m._eod_handoff_present(now) is False          # only morning + 1pm -> no EOD
    (bd / "2026-06-10Teod.md").write_text("eod")
    assert m._eod_handoff_present(now) is True            # eod slot present


def test_eod_present_accepts_1600_slot(tmp_path, monkeypatch):
    import datetime
    from runner.ledger.market_clock import _ET
    bd = tmp_path / "bridge"; bd.mkdir()
    monkeypatch.setattr(tb, "BRIDGE_MD_DIR", bd)
    (bd / "2026-06-10T1600.md").write_text("eod")
    assert m._eod_handoff_present(datetime.datetime(2026, 6, 10, 18, 0, tzinfo=_ET)) is True
