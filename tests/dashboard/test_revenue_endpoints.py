import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.ledger import revenue as rev
from runner.tools import revenue_tool as rt


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")
    monkeypatch.setattr(rt, "REVENUE_MD", tmp_path / "ledger.md")
    return TestClient(server.app)


def test_log_revenue_endpoint(client, tmp_path):
    r = client.post("/api/revenue/log",
                    json={"pod": "ai-x", "amount_usd": 49.0, "source": "manual", "kind": "manual"})
    assert r.json()["success"] is True
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.0)


def test_log_revenue_endpoint_bad_amount(client):
    r = client.post("/api/revenue/log",
                    json={"pod": "ai-x", "amount_usd": "abc", "source": "manual"})
    assert "error" in r.json()


def test_pnl_returns_pod_rows(client, monkeypatch):
    monkeypatch.setattr(server, "read_opportunities",
                        lambda: [{"slug": "ai-x", "pod": "ai-x", "est_rev_mo": "500",
                                  "composite": "80", "phase": "graduated", "poc": "promising",
                                  "system_fit": "7", "status": "graduated", "updated": "2026-05-28"}])
    client.post("/api/revenue/log",
                json={"pod": "ai-x", "amount_usd": 120.0, "source": "manual", "kind": "manual"})
    r = client.get("/api/pnl")
    rows = r.json()["pods"]
    row = next(p for p in rows if p["pod"] == "ai-x")
    assert row["revenue_to_date"] == pytest.approx(120.0)
    assert row["est_rev_mo"] == pytest.approx(500.0)
