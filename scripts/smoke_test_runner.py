from unittest.mock import patch, MagicMock
from runner.main import run_cycle

mock_result = {
    "task_id": "SAMPLE-001",
    "output": "Smoke test output.",
    "cost_usd": 0.0,
    "role_id": "debug_worker",
    "input_tokens": 0,
    "output_tokens": 0,
}

with patch("runner.main.is_budget_exceeded", return_value=False):
    with patch("runner.main.read_todo_tasks", return_value=[{
        "task_id": "SAMPLE-001",
        "task_type": "validation",
        "assigned_agent": "debug_worker",
        "body": "Smoke test.",
        "file_path": "workspace/tasks/todo/SAMPLE-001.md",
    }]):
        with patch("runner.main.acquire_lock", return_value=True):
            with patch("runner.main.release_lock"):
                with patch("runner.main.move_task"):
                    with patch("runner.main.write_task_output"):
                        with patch("runner.main.AgentBase") as MockAgent:
                            MockAgent.return_value.run.return_value = mock_result
                            run_cycle()

import json
from pathlib import Path
state = json.loads(Path("workspace/dashboard-state.json").read_text())
print("State file written OK")
print(f"  Agents: {list(state['agents'].keys())}")
print(f"  Budget: ${state['budget']['spent_usd']} / ${state['budget']['cap_usd']}")
