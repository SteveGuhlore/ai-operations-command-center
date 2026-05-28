# tests/runner/test_opportunity_chain.py
import importlib


def test_spec_append_and_promotion_threshold(tmp_path, monkeypatch):
    import runner.tools.opportunity as opp
    importlib.reload(opp)
    monkeypatch.setattr(opp, "OPP_DIR", tmp_path / "opportunities")
    monkeypatch.setattr(opp, "LEDGER_FILE", tmp_path / "opportunities" / "ledger.md")
    opp.log_opportunity(slug="svc", one_liner="x", problem="p", who_pays="w",
                        willingness_to_pay=9, revenue_potential=8, problem_severity=8,
                        buildability=8, system_fit=8, novelty=7)
    page = opp.OPP_DIR / "svc.md"
    assert "_pending (P2)_" in page.read_text(encoding="utf-8")
    page.write_text(page.read_text(encoding="utf-8").replace(
        "## Build Spec\n_pending (P2)_", "## Build Spec\nInputs: review text. Output: reply draft."
    ), encoding="utf-8")
    assert "reply draft" in page.read_text(encoding="utf-8")
    assert opp.composite_score(9, 8, 8, 8, 8, 7) >= 75
