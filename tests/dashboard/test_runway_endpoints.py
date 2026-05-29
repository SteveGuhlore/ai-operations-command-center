import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.ledger import runway as rw


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(rw, "RUNWAY_FILE", tmp_path / "runway.json")
    monkeypatch.setattr(rw, "_real_revenue", lambda: 0.0)
    monkeypatch.setattr(rw, "_pod_spend", lambda: 0.0)
    return TestClient(server.app)


def test_get_runway(client):
    d = client.get("/api/runway").json()
    assert d["status"] == "alive"
    assert "days_remaining" in d
    assert "survive_by" in d
    assert d["real_revenue"] == 0.0


def test_revive_endpoint(client):
    rw.pause_pod()
    assert client.get("/api/runway").json()["status"] == "paused"
    r = client.post("/api/runway/revive")
    assert r.json()["status"] == "alive"
    assert client.get("/api/runway").json()["status"] == "alive"
