from contextlib import ExitStack
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


# Everything run_cycle calls besides the dispatch logic under test. Without these stubs the
# test executes the REAL side effects against the repo workspace — scan_tony_bridge ingests
# the checked-in bridge/ files and spawns dozens of TONY-* tasks into workspace/tasks/todo,
# the equity snapshot / schedulers write state json — polluting the working tree on every run.
_CYCLE_SIDE_EFFECTS = [
    "_maybe_handle_telegram_chat", "_reap_stale_tasks", "_maybe_refresh_regime",
    "scan_tony_bridge", "_maybe_spawn_planning_task", "_advance_opportunity_pipeline",
    "_maybe_run_learning", "_maybe_run_tony_self_review", "_maybe_stage_research_wave",
    "_maybe_stage_research_followups", "_maybe_send_daily_summary",
    "_maybe_send_weekly_synthesis",
]


def _isolated_cycle(stack: ExitStack):
    for name in _CYCLE_SIDE_EFFECTS:
        stack.enter_context(patch(f"runner.main.{name}", MagicMock()))
    stack.enter_context(patch("runner.ledger.equity_history.snapshot", MagicMock()))
    stack.enter_context(patch("runner.ledger.alpaca_paper.sync",
                              MagicMock(return_value={"status": "no_keys"})))
    stack.enter_context(patch("runner.ledger.alpaca_paper.reconcile_realized", MagicMock()))


def test_run_cycle_skips_when_budget_exceeded():
    with ExitStack() as stack:
        _isolated_cycle(stack)
        stack.enter_context(patch("runner.main.is_budget_exceeded", return_value=True))
        mock_read = stack.enter_context(patch("runner.main.read_todo_tasks"))
        from runner.main import run_cycle
        run_cycle()
        mock_read.assert_not_called()


def test_run_cycle_dispatches_tasks():
    mock_result = {"task_id": "TEST-001", "output": "done", "cost_usd": 0.01}
    with ExitStack() as stack:
        _isolated_cycle(stack)
        stack.enter_context(patch("runner.main.is_budget_exceeded", return_value=False))
        stack.enter_context(patch("runner.main.read_todo_tasks", return_value=[_make_task()]))
        mock_run = stack.enter_context(patch("runner.main.run_task", return_value=mock_result))
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
