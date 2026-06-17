# runner/ledger/budget.py
import json
import math
from datetime import date
from pathlib import Path


def _clean_cost(cost_usd: float) -> float:
    """Spend can only ever ADD to the meter. Reject negative or non-finite values
    so a stray refund/NaN/inf can't lower the running total and bypass the cap."""
    try:
        c = float(cost_usd)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(c) or c < 0:
        return 0.0
    return c

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
    cost_usd = _clean_cost(cost_usd)
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


def get_offhours_cap() -> float:
    """Separate high/uncapped lane for the off-market research wave so it can run past the daytime
    cap ("token-maxx" the research). Default infinite; set TONY_OFFHOURS_BUDGET_USD to bound it."""
    import os
    raw = os.environ.get("TONY_OFFHOURS_BUDGET_USD", "").strip()
    if not raw:
        return float("inf")
    try:
        return float(raw)
    except ValueError:
        return float("inf")


def is_budget_exceeded(off_hours: bool = False) -> bool:
    """Daytime (off_hours=False) uses the normal daily cap — unchanged. The off-hours research lane
    consults its own separate cap so a depleted daytime budget never aborts the overnight wave."""
    cap = get_offhours_cap() if off_hours else get_daily_cap()
    return get_daily_spend() >= cap


def is_pod_budget_exceeded(pod: str) -> bool:
    return get_pod_spend(pod) >= get_pod_cap(pod)
