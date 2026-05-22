from pathlib import Path
import pytest
from runner.tasks.reader import parse_task_file, read_todo_tasks

SAMPLE_TASK = """\
---
task_id: TEST-001
assigned_agent: debug_worker
status: todo
priority: high
pod: app_saas_pod
task_type: validation
---

# Test Task

## Goal
Check environment.
"""

def test_parse_task_file_extracts_frontmatter(tmp_path):
    task_file = tmp_path / "TEST-001-test.md"
    task_file.write_text(SAMPLE_TASK, encoding="utf-8")
    task = parse_task_file(task_file)
    assert task["task_id"] == "TEST-001"
    assert task["assigned_agent"] == "debug_worker"
    assert task["status"] == "todo"
    assert task["task_type"] == "validation"

def test_parse_task_file_includes_body(tmp_path):
    task_file = tmp_path / "TEST-001-test.md"
    task_file.write_text(SAMPLE_TASK, encoding="utf-8")
    task = parse_task_file(task_file)
    assert "Check environment" in task["body"]

def test_parse_task_file_raises_on_bad_format(tmp_path):
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("no frontmatter here", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid task format"):
        parse_task_file(bad_file)

def test_read_todo_tasks_returns_list(tmp_path, monkeypatch):
    todo_dir = tmp_path / "workspace" / "tasks" / "todo"
    todo_dir.mkdir(parents=True)
    (todo_dir / "TEST-001-test.md").write_text(SAMPLE_TASK, encoding="utf-8")

    import runner.tasks.reader as reader_module
    monkeypatch.setattr(reader_module, "TASKS_DIR", tmp_path / "workspace" / "tasks")

    tasks = read_todo_tasks()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "TEST-001"
