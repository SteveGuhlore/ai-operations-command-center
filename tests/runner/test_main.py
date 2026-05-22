from unittest.mock import patch, MagicMock
import pytest


def _make_task(task_id="TEST-001", task_type="validation", assigned="debug_worker"):
    return {
        "task_id": task_id,
        "task_type": task_type,
        "assigned_agent": assigned,
        "body": "Check environment.",
        "file_path": f"workspace/tasks/todo/{task_id}-test.md",
    }


def test_run_cycle_skips_when_budget_exceeded():
    with patch("runner.main.is_budget_exceeded", return_value=True):
        with patch("runner.main.read_todo_tasks") as mock_read:
            from runner.main import run_cycle
            run_cycle()
            mock_read.assert_not_called()


def test_run_cycle_dispatches_tasks():
    mock_result = {"task_id": "TEST-001", "output": "done", "cost_usd": 0.01}
    with patch("runner.main.is_budget_exceeded", return_value=False):
        with patch("runner.main.read_todo_tasks", return_value=[_make_task()]):
            with patch("runner.main.run_task", return_value=mock_result) as mock_run:
                from runner.main import run_cycle
                run_cycle()
                mock_run.assert_called_once()


def test_run_task_acquires_lock_and_calls_agent():
    mock_result = {"task_id": "TEST-001", "output": "done", "cost_usd": 0.01,
                   "role_id": "debug_worker", "input_tokens": 100, "output_tokens": 50}
    with patch("runner.main.acquire_lock", return_value=True):
        with patch("runner.main.release_lock"):
            with patch("runner.main.move_task"):
                with patch("runner.main.write_task_output"):
                    with patch("runner.main.update_agent_state"):
                        with patch("runner.main.AgentBase") as mock_agent_cls:
                            mock_agent = MagicMock()
                            mock_agent.run.return_value = mock_result
                            mock_agent_cls.return_value = mock_agent
                            from runner.main import run_task
                            result = run_task(_make_task())
                            assert result["task_id"] == "TEST-001"


def test_run_task_skips_when_already_locked():
    with patch("runner.main.acquire_lock", return_value=False):
        from runner.main import run_task
        result = run_task(_make_task())
        assert result.get("skipped") is True
