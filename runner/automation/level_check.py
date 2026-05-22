import yaml
from pathlib import Path

LEVEL_FILE = Path(__file__).parent.parent.parent / "config" / "automation-level.yaml"


def _load() -> dict:
    try:
        with open(LEVEL_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {"current_level": 2, "level_3_actions": {}}


def get_automation_level() -> int:
    return int(_load().get("current_level", 2))


def is_action_allowed(action_name: str) -> bool:
    config = _load()
    level_3_actions: dict = config.get("level_3_actions", {})
    if action_name not in level_3_actions:
        return True
    return bool(level_3_actions.get(action_name, False))
