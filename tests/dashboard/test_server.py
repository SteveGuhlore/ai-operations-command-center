import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def state_file(tmp_path):
    f = tmp_path / "dashboard-state.json"
    f.write_text(json.dumps({
        "updated_at": 1700000000.0,
        "agents": {
            "manager": {"state": "idle", "task_id": "", "last_action": "completed TASK-001", "updated_at": 1700000000.0}
        },
        "tasks": {"todo": 3, "in_progress": 1, "review": 0, "done": 10, "failed": 0},
        "budget": {"spent_usd": 2.14, "cap_usd": 50.0},
    }), encoding="utf-8")
    return f


def _make_client(state_file):
    import dashboard.server as server_module
    from importlib import reload
    reload(server_module)
    server_module.STATE_FILE = state_file
    return TestClient(server_module.app)


def test_get_state_returns_json(state_file):
    client = _make_client(state_file)
    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agents"]["manager"]["state"] == "idle"
    assert data["tasks"]["todo"] == 3
    assert data["budget"]["spent_usd"] == pytest.approx(2.14)


def test_get_root_returns_html(state_file):
    client = _make_client(state_file)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_get_state_returns_empty_when_file_missing(tmp_path):
    import dashboard.server as server_module
    from importlib import reload
    reload(server_module)
    server_module.STATE_FILE = tmp_path / "nonexistent.json"
    client = TestClient(server_module.app)
    resp = client.get("/state")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_followup_sweep_creates_outreach_task(state_file, tmp_path, monkeypatch):
    import runner.tools.task_creator as tc
    from importlib import reload
    reload(tc)
    monkeypatch.setattr(tc, "TASKS_DIR", tmp_path / "tasks")
    monkeypatch.setattr(tc, "_has_pending_task", lambda *a, **k: False)
    monkeypatch.setattr(tc, "spawn_allowed", lambda *a, **k: (True, ""))
    monkeypatch.setattr(tc, "record_spawn", lambda *a, **k: None)

    client = _make_client(state_file)
    resp = client.post("/api/outreach/followup-sweep")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data["task_id"].startswith("AUTO-")

    todo = tmp_path / "tasks" / "todo"
    files = list(todo.glob("*.md"))
    assert len(files) == 1
    body = files[0].read_text(encoding="utf-8")
    assert "assigned_agent: outreach_worker" in body
    assert "pod: local_outreach_pod" in body
