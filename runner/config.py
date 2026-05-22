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
