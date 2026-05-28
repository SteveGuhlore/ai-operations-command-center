import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def _load(relative_path: str) -> dict:
    path = BASE_DIR / relative_path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_agents() -> dict:
    return _load("config/agents.yaml")


def load_budgets() -> dict:
    return _load("config/budgets.yaml")


def load_automation_level() -> dict:
    return _load("config/automation-level.yaml")


def load_spawn_schedules() -> dict:
    """Per-agent/task-type spawn cadence config. Returns {} if the file is
    absent so an unconfigured deployment enforces nothing (zero behavior change)."""
    path = BASE_DIR / "config/spawn-schedules.yaml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("spawn_schedules", {})
