# runner/ledger/budget.py
import json
from datetime import date
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
SPEND_FILE = LEDGER_DIR / "daily-spend.json"


def _load_spend() -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not SPEND_FILE.exists():
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}, "by_pod": {}}
    data = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}, "by_pod": {}}
    data.setdefault("by_pod", {})
    return data


def _save_spend(data: dict) -> None:
    SPEND_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_spend(role_id: str, cost_usd: float, pod: str | None = None) -> None:
    data = _load_spend()
    data["total_usd"] = round(data["total_usd"] + cost_usd, 6)
    data["by_role"][role_id] = round(data["by_role"].get(role_id, 0.0) + cost_usd, 6)
    if pod:
        data["by_pod"][pod] = round(data["by_pod"].get(pod, 0.0) + cost_usd, 6)
    _save_spend(data)


def get_daily_spend() -> float:
    return _load_spend()["total_usd"]


def get_pod_spend(pod: str) -> float:
    return _load_spend().get("by_pod", {}).get(pod, 0.0)


def get_daily_cap() -> float:
    from runner.config import load_budgets
    return load_budgets()["budgets"]["daily_limits"]["total_spend_limit_usd"]


def get_pod_cap(pod: str) -> float:
    from runner.config import load_budgets
    limits = load_budgets()["budgets"].get("per_pod_limits", {})
    pod_cfg = limits.get(pod)
    if not pod_cfg:
        return float("inf")
    return float(pod_cfg.get("daily_spend_limit_usd", float("inf")))


def get_poc_cap(pod: str = "opportunity_pod") -> float:
    """Hard per-PoC dollar envelope. Reads
    per_pod_limits.<pod>.per_poc_limit_usd from budgets.yaml; falls back to
    $2 if unset so a PoC can never run uncapped."""
    from runner.config import load_budgets
    limits = load_budgets()["budgets"].get("per_pod_limits", {})
    cap = (limits.get(pod) or {}).get("per_poc_limit_usd")
    return float(cap) if cap is not None else 2.0


def get_poc_run_cost(pod: str = "opportunity_pod") -> float:
    """Cost charged to a PoC's envelope per subprocess invocation. A PowerShell
    PoC run has no directly-measurable API cost, so we charge a flat estimate to
    keep the meter monotonic — that is what makes the cap a real ceiling on a
    runaway loop rather than an unbounded number of free runs. Configurable via
    per_pod_limits.<pod>.per_poc_run_cost_usd; defaults to $0.05 (~40 runs/$2)."""
    from runner.config import load_budgets
    limits = load_budgets()["budgets"].get("per_pod_limits", {})
    cost = (limits.get(pod) or {}).get("per_poc_run_cost_usd")
    return float(cost) if cost is not None else 0.05


def is_budget_exceeded() -> bool:
    return get_daily_spend() >= get_daily_cap()


def is_pod_budget_exceeded(pod: str) -> bool:
    return get_pod_spend(pod) >= get_pod_cap(pod)
