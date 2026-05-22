# runner/tasks/router.py
from runner.config import load_agents

_routing_table: dict[str, str] | None = None


def _build_routing_table() -> dict[str, str]:
    agents_data = load_agents()
    table: dict[str, str] = {}
    for agent in agents_data["agents"]:
        role_id = agent["role_id"]
        for task_type in agent.get("allowed_task_types", []):
            if task_type not in table:
                table[task_type] = role_id
    return table


def route_task(task: dict) -> str:
    global _routing_table
    if _routing_table is None:
        _routing_table = _build_routing_table()

    task_type = task.get("task_type")
    if task_type and task_type in _routing_table:
        return _routing_table[task_type]

    assigned = task.get("assigned_agent")
    if assigned:
        return assigned

    return "debug_worker"
