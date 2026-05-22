import json
from pathlib import Path
from runner.state import writer as writer_module


def _patch_writer(monkeypatch, tmp_path):
    state_file = tmp_path / "dashboard-state.json"
    monkeypatch.setattr(writer_module, "STATE_FILE", state_file)
    monkeypatch.setattr(writer_module, "_agent_states", {})
    monkeypatch.setattr(writer_module, "get_daily_spend", lambda: 2.14)
    monkeypatch.setattr(writer_module, "get_daily_cap", lambda: 50.0)
    monkeypatch.setattr(writer_module, "_count_tasks", lambda: {
        "todo": 5, "in_progress": 2, "review": 1, "done": 10, "failed": 0
    })
    return state_file


def test_update_agent_state_writes_file(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("debug_worker", "working", "TASK-001")
    data = json.loads(state_file.read_text())
    assert data["agents"]["debug_worker"]["state"] == "working"
    assert data["agents"]["debug_worker"]["task_id"] == "TASK-001"


def test_state_file_includes_budget(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("manager", "idle")
    data = json.loads(state_file.read_text())
    assert data["budget"]["spent_usd"] == 2.14
    assert data["budget"]["cap_usd"] == 50.0


def test_state_file_includes_task_counts(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("manager", "idle")
    data = json.loads(state_file.read_text())
    assert data["tasks"]["todo"] == 5
    assert data["tasks"]["done"] == 10
