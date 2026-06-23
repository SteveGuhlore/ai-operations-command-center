import math
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def _load(relative_path: str) -> dict:
    path = BASE_DIR / relative_path
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # An empty/whitespace-only file parses to None and a stray scalar to a non-dict.
    # Returning either silently lets callers treat a truncated config as "no settings"
    # — for budgets.yaml that quietly disarms the spend cap on a live 24/7 trader.
    # Fail loudly at the boundary instead of degrading into uncapped behavior.
    if data is None:
        raise ValueError(f"config {relative_path} is empty or not valid YAML")
    if not isinstance(data, dict):
        raise ValueError(
            f"config {relative_path} must be a YAML mapping, got {type(data).__name__}"
        )
    return data


def load_agents() -> dict:
    return _load("config/agents.yaml")


def load_budgets() -> dict:
    data = _load("config/budgets.yaml")
    # budgets.yaml is a safety control, not just config: a missing or garbage daily
    # cap must never be read as "uncapped". Verify the one number every spend gate
    # ultimately depends on before any of them trust it.
    try:
        cap = data["budgets"]["daily_limits"]["total_spend_limit_usd"]
    except (KeyError, TypeError):
        raise ValueError(
            "config/budgets.yaml missing budgets.daily_limits.total_spend_limit_usd"
        )
    if (
        isinstance(cap, bool)
        or not isinstance(cap, (int, float))
        or not math.isfinite(cap)
        or cap <= 0
    ):
        raise ValueError(
            f"config/budgets.yaml total_spend_limit_usd must be a positive finite "
            f"number, got {cap!r}"
        )
    return data


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
