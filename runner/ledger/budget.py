# runner/ledger/budget.py
import json
from datetime import date
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
SPEND_FILE = LEDGER_DIR / "daily-spend.json"


def _load_spend() -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not SPEND_FILE.exists():
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}}
    data = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}}
    return data


def _save_spend(data: dict) -> None:
    SPEND_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_spend(role_id: str, cost_usd: float) -> None:
    data = _load_spend()
    data["total_usd"] = round(data["total_usd"] + cost_usd, 6)
    data["by_role"][role_id] = round(data["by_role"].get(role_id, 0.0) + cost_usd, 6)
    _save_spend(data)


def get_daily_spend() -> float:
    return _load_spend()["total_usd"]


def get_daily_cap() -> float:
    from runner.config import load_budgets
    return load_budgets()["budgets"]["daily_limits"]["total_spend_limit_usd"]


def is_budget_exceeded() -> bool:
    return get_daily_spend() >= get_daily_cap()
