import pytest
from runner.tools import opportunity as opp


def _seed_ledger(tmp_path, monkeypatch, slug="ai-x"):
    opp_dir = tmp_path / "opportunities"
    opp_dir.mkdir(parents=True)
    monkeypatch.setattr(opp, "OPP_DIR", opp_dir)
    monkeypatch.setattr(opp, "LEDGER_FILE", opp_dir / "ledger.md")
    ledger = (
        "# Opportunity Ledger\n\n"
        "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
        "|------|-----------|-------|-----|-----------|-----------|--------|-----|--------|\n"
        f"| {slug} | 80.0 | deepdived | — | 7 | 500 | deepdived | — | 2026-05-28 |\n"
    )
    (opp_dir / "ledger.md").write_text(ledger, encoding="utf-8")
    (opp_dir / f"{slug}.md").write_text(
        f"# {slug}\n\n## PoC Grade\n_pending (P3)_\n", encoding="utf-8")
    return opp_dir


def test_grade_poc_updates_ledger_poc_column(tmp_path, monkeypatch):
    opp_dir = _seed_ledger(tmp_path, monkeypatch)
    out = opp.grade_poc("ai-x", "promising", "demo works end to end")
    assert out["success"] is True
    ledger = (opp_dir / "ledger.md").read_text()
    row = [l for l in ledger.splitlines() if l.startswith("| ai-x |")][0]
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[3] == "promising"   # poc column
    assert cells[2] == "graded"      # phase column


def test_grade_poc_errors_when_slug_not_in_ledger(tmp_path, monkeypatch):
    _seed_ledger(tmp_path, monkeypatch)
    out = opp.grade_poc("does-not-exist", "promising", "typo slug")
    assert "error" in out
    assert "success" not in out


def test_grade_poc_rejects_bad_verdict(tmp_path, monkeypatch):
    _seed_ledger(tmp_path, monkeypatch)
    out = opp.grade_poc("ai-x", "great", "bad verdict value")
    assert "error" in out
