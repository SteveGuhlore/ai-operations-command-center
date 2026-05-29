# runner/ledger/runway.py
"""Prospector survival runway — the 'doomsday clock'.

opportunity_pod runs on a finite runway that BURNS DOWN with spend/time and is
EXTENDED only by REAL logged revenue (the operator/Stripe revenue ledger, which
no agent can write). When the runway expires the pipeline auto-pauses; an
operator revives it. Parallel to budget.py — never merged, never touches it.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
RUNWAY_FILE = LEDGER_DIR / "runway.json"

_DEFAULTS = {
    "base_grace_days": 14,
    "days_per_real_dollar": 1.0,
    "spend_allowance_usd": 20.0,
    "usd_per_real_dollar": 1.0,
    "status": "alive",
    "paused_at": None,
    "revived_count": 0,
}


def _load() -> dict:
    """Read state, merged over safe defaults. A missing/corrupt file defaults to
    ALIVE with today's start + base grace — a runway bug can never silently brick
    the pod, nor let it run forever (the grace deadline still applies)."""
    state = dict(_DEFAULTS)
    state["started_at"] = date.today().isoformat()
    if RUNWAY_FILE.exists():
        try:
            disk = json.loads(RUNWAY_FILE.read_text(encoding="utf-8"))
            if isinstance(disk, dict):
                state.update(disk)
        except (json.JSONDecodeError, OSError):
            pass
    return state


def _save(state: dict) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    RUNWAY_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _real_revenue() -> float:
    """Real logged revenue attributable to Prospector: opportunity_pod itself
    plus any pod a Prospector idea graduated into (ledger `pod` column)."""
    from runner.ledger.revenue import get_pod_revenue
    from runner.tools.opportunity import read_ledger
    pods = {"opportunity_pod"}
    try:
        for row in read_ledger():
            p = (row.get("pod") or "").strip()
            if p and p not in ("—", "-"):
                pods.add(p)
    except Exception:
        pass
    return round(sum(get_pod_revenue(p) for p in pods), 2)


def _pod_spend() -> float:
    from runner.ledger.budget import get_pod_spend
    return get_pod_spend("opportunity_pod")


def compute_runway() -> dict:
    """Full computed runway view for the gate and the dashboard."""
    s = _load()
    revenue = _real_revenue()
    spend = _pod_spend()

    started = date.fromisoformat(s["started_at"])
    grace = float(s["base_grace_days"]) + revenue * float(s["days_per_real_dollar"])
    deadline = started + timedelta(days=grace)
    days_remaining = (deadline - date.today()).days
    time_expired = date.today() > deadline

    effective_allowance = float(s["spend_allowance_usd"]) + revenue * float(s["usd_per_real_dollar"])
    budget_expired = spend >= effective_allowance

    paused = s.get("status") == "paused"
    expired = paused or time_expired or budget_expired

    return {
        "status": "paused" if paused else ("expired" if expired else "alive"),
        "expired": expired,
        "days_remaining": days_remaining,
        "survive_by": deadline.isoformat(),
        "real_revenue": revenue,
        "spend": round(spend, 2),
        "effective_allowance_usd": round(effective_allowance, 2),
        "revived_count": s.get("revived_count", 0),
        "paused_at": s.get("paused_at"),
    }


def runway_expired() -> bool:
    return compute_runway()["expired"]


def pause_pod() -> dict:
    """Mark the pod paused (the 'plug pull'). Idempotent — reversible via revive()."""
    s = _load()
    if s.get("status") != "paused":
        s["status"] = "paused"
        s["paused_at"] = datetime.now().isoformat(timespec="seconds")
        _save(s)
    return compute_runway()


def revive() -> dict:
    """Operator action: reset the clock and bring the pod back to life."""
    s = _load()
    s["status"] = "alive"
    s["paused_at"] = None
    s["started_at"] = date.today().isoformat()
    s["revived_count"] = int(s.get("revived_count", 0)) + 1
    _save(s)
    return compute_runway()
