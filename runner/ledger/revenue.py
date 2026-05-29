# runner/ledger/revenue.py
import json
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
REVENUE_FILE = LEDGER_DIR / "revenue.json"


def _load() -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not REVENUE_FILE.exists():
        return {"by_pod": {}, "total_usd": 0.0, "seen_external_ids": []}
    try:
        data = json.loads(REVENUE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_pod": {}, "total_usd": 0.0, "seen_external_ids": []}
    data.setdefault("by_pod", {})
    data.setdefault("total_usd", 0.0)
    data.setdefault("seen_external_ids", [])
    return data


def _save(data: dict) -> None:
    REVENUE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_revenue(pod: str, amount_usd: float, source: str, external_id: str,
                   kind: str = "sale") -> dict:
    """Append a revenue event to the machine mirror. Dedup is keyed on a
    non-empty external_id (Stripe charge id); manual/adjustment rows pass an
    empty external_id and are never deduped. Returns {recorded: bool}."""
    data = _load()
    if external_id and external_id in data["seen_external_ids"]:
        return {"recorded": False, "reason": "duplicate external_id", "external_id": external_id}
    data["total_usd"] = round(data["total_usd"] + amount_usd, 6)
    data["by_pod"][pod] = round(data["by_pod"].get(pod, 0.0) + amount_usd, 6)
    if external_id:
        data["seen_external_ids"].append(external_id)
    _save(data)
    return {"recorded": True, "pod": pod, "amount_usd": amount_usd, "kind": kind}


def get_pod_revenue(pod: str) -> float:
    return _load()["by_pod"].get(pod, 0.0)


def get_revenue_total() -> float:
    return _load()["total_usd"]
