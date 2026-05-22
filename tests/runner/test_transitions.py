# tests/runner/test_transitions.py
import pytest
from pathlib import Path
from runner.tasks import transitions as trans_module

SAMPLE_TASK = """\
---
task_id: TEST-001
assigned_agent: debug_worker
status: todo
priority: high
---

# Test Task
"""

def _setup_task(base: Path, status: str) -> Path:
    folder = base / status
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "TEST-001-test.md"
    f.write_text(SAMPLE_TASK, encoding="utf-8")
    return f


def test_move_task_moves_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    _setup_task(tmp_path, "todo")
    dst = trans_module.move_task("TEST-001", "todo", "in_progress")
    assert dst.exists()
    assert not (tmp_path / "todo" / "TEST-001-test.md").exists()


def test_move_task_updates_status_in_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    _setup_task(tmp_path, "todo")
    dst = trans_module.move_task("TEST-001", "todo", "in_progress")
    content = dst.read_text(encoding="utf-8")
    assert "status: in_progress" in content


def test_move_task_raises_if_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    (tmp_path / "todo").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        trans_module.move_task("MISSING-999", "todo", "in_progress")


def test_write_task_output_appends_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    folder = tmp_path / "in_progress"
    folder.mkdir(parents=True)
    (folder / "TEST-001-test.md").write_text(SAMPLE_TASK, encoding="utf-8")
    trans_module.write_task_output("TEST-001", "All checks passed.", "in_progress")
    content = (folder / "TEST-001-test.md").read_text(encoding="utf-8")
    assert "All checks passed." in content
    assert "## Agent Output" in content
