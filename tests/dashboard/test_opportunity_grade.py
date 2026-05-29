import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.tools import opportunity as opp


@pytest.fixture
def client(tmp_path, monkeypatch):
    opp_dir = tmp_path / "opportunities"
    opp_dir.mkdir(parents=True)
    monkeypatch.setattr(opp, "OPP_DIR", opp_dir)
    monkeypatch.setattr(opp, "LEDGER_FILE", opp_dir / "ledger.md")
    (opp_dir / "ledger.md").write_text(
        "# Opportunity Ledger\n\n"
        "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| ai-x | 80.0 | deepdived | — | 7 | 500 | deepdived | — | 2026-05-28 |\n",
        encoding="utf-8")
    (opp_dir / "ai-x.md").write_text(
        "# ai-x\n\n## PoC Grade\n_pending (P3)_\n", encoding="utf-8")
    return TestClient(server.app)


def test_grade_endpoint_records_verdict(client, tmp_path):
    r = client.post("/api/opportunity/grade",
                    json={"slug": "ai-x", "verdict": "promising", "reason": "demo works"})
    assert r.json()["success"] is True
    ledger = (tmp_path / "opportunities" / "ledger.md").read_text()
    assert "promising" in ledger


def test_grade_endpoint_bad_slug_errors(client):
    r = client.post("/api/opportunity/grade",
                    json={"slug": "does-not-exist", "verdict": "promising", "reason": "x"})
    assert "error" in r.json()


def test_grade_endpoint_requires_slug(client):
    r = client.post("/api/opportunity/grade", json={"verdict": "promising", "reason": "x"})
    assert "error" in r.json()
