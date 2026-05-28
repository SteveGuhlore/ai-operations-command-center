# tests/runner/test_opportunity_tools.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.opportunity as opp
    importlib.reload(opp)
    monkeypatch.setattr(opp, "OPP_DIR", tmp_path / "opportunities")
    monkeypatch.setattr(opp, "LEDGER_FILE", tmp_path / "opportunities" / "ledger.md")
    return opp


def test_composite_score_math(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    score = opp.composite_score(
        willingness_to_pay=8, revenue_potential=8, problem_severity=8,
        buildability=8, system_fit=8, novelty=8,
    )
    assert score == 80.0


def test_composite_score_weighting(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    score = opp.composite_score(
        willingness_to_pay=10, revenue_potential=0, problem_severity=0,
        buildability=0, system_fit=0, novelty=0,
    )
    assert score == 25.0


def test_log_opportunity_writes_ledger_and_page(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    res = opp.log_opportunity(
        slug="ai-review-reply-agent",
        one_liner="Auto-replies to Google reviews for local businesses",
        problem="SMBs ignore reviews",
        who_pays="MA service businesses",
        willingness_to_pay=8, revenue_potential=7, problem_severity=7,
        buildability=8, system_fit=9, novelty=6,
    )
    assert res["success"] is True
    assert res["composite"] == opp.composite_score(8, 7, 7, 8, 9, 6)
    ledger = opp.LEDGER_FILE.read_text(encoding="utf-8")
    assert "ai-review-reply-agent" in ledger
    assert "| scouted |" in ledger
    page = (opp.OPP_DIR / "ai-review-reply-agent.md").read_text(encoding="utf-8")
    assert "system_fit" in page
    assert "[[ledger]]" in page


def test_log_opportunity_dedup(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    opp.log_opportunity(slug="dup-idea", one_liner="x", problem="p", who_pays="w",
                        willingness_to_pay=5, revenue_potential=5, problem_severity=5,
                        buildability=5, system_fit=5, novelty=5)
    res2 = opp.log_opportunity(slug="dup-idea", one_liner="x", problem="p", who_pays="w",
                               willingness_to_pay=5, revenue_potential=5, problem_severity=5,
                               buildability=5, system_fit=5, novelty=5)
    assert res2.get("skipped") is True
    ledger = opp.LEDGER_FILE.read_text(encoding="utf-8")
    assert ledger.count("| dup-idea |") == 1
