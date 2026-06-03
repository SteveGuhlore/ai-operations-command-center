from runner.tools import market_regime as mr
from runner.tools import tony_ideas as ti
from runner.ledger import tony_live_guard as guard


# ---- Phase 4: market regime ----
def test_regime_risk_on(monkeypatch):
    monkeypatch.setattr(mr, "_fetch", lambda: {"vix": 14.0, "spy_above_sma50": True,
                                               "sector_rs": {"XLK": 1.2, "XLE": -0.3}})
    r = mr.get_market_regime()
    assert r["regime"] == "risk_on"
    assert "Tech (XLK)" in r["leaders"]


def test_regime_risk_off_on_high_vix(monkeypatch):
    monkeypatch.setattr(mr, "_fetch", lambda: {"vix": 30.0, "spy_above_sma50": True, "sector_rs": {}})
    assert mr.get_market_regime()["regime"] == "risk_off"


def test_regime_risk_off_when_spy_below_sma(monkeypatch):
    monkeypatch.setattr(mr, "_fetch", lambda: {"vix": 15.0, "spy_above_sma50": False, "sector_rs": {}})
    assert mr.get_market_regime()["regime"] == "risk_off"


# ---- Phase 5: idea channel ----
def test_log_idea_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(ti, "IDEAS_FILE", tmp_path / "ideas.json")
    r = ti.log_tony_idea(symbol="smci", thesis="x", source="own_pattern", score=72)
    assert r.get("success") and r["symbol"] == "SMCI"


def test_log_idea_bad_source(tmp_path, monkeypatch):
    monkeypatch.setattr(ti, "IDEAS_FILE", tmp_path / "ideas.json")
    assert "error" in ti.log_tony_idea(symbol="X", thesis="x", source="moon")


# ---- Phase 6: live guard ----
def test_live_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TONY_LIVE_ENABLED", raising=False)
    assert guard.live_allowed({"tony_win_rate": 99, "graded": 100})["allowed"] is False


def test_live_requires_enable_and_record(monkeypatch, tmp_path):
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    monkeypatch.setattr(guard, "KILL_SWITCH", tmp_path / "no_kill")
    assert guard.live_allowed({"tony_win_rate": 50, "graded": 10})["allowed"] is False
    assert guard.live_allowed({"tony_win_rate": 62, "graded": 60})["allowed"] is True


def test_kill_switch_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("TONY_LIVE_ENABLED", "1")
    ks = tmp_path / "kill"; ks.write_text("stop")
    monkeypatch.setattr(guard, "KILL_SWITCH", ks)
    assert guard.live_allowed({"tony_win_rate": 99, "graded": 100})["allowed"] is False
