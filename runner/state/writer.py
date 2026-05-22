import json
import time
from pathlib import Path
from runner.ledger.budget import get_daily_spend, get_daily_cap

STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "dashboard-state.json"

_agent_states: dict[str, dict] = {}


def _count_tasks() -> dict:
    base = Path(__file__).parent.parent.parent / "workspace" / "tasks"
    statuses = ["todo", "in_progress", "review", "done", "failed"]
    return {s: len(list((base / s).glob("*.md"))) for s in statuses}


def update_agent_state(
    role_id: str,
    state: str,
    task_id: str = "",
    last_action: str = "",
) -> None:
    _agent_states[role_id] = {
        "state": state,
        "task_id": task_id,
        "last_action": last_action,
        "updated_at": time.time(),
    }
    _flush()


def _flush() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "updated_at": time.time(),
        "agents": _agent_states,
        "tasks": _count_tasks(),
        "budget": {
            "spent_usd": get_daily_spend(),
            "cap_usd": get_daily_cap(),
        },
    }, indent=2), encoding="utf-8")
