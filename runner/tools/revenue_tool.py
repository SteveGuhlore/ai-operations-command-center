# runner/tools/revenue_tool.py
from datetime import datetime
from pathlib import Path

from runner.ledger.revenue import record_revenue

REVENUE_MD = Path(__file__).parent.parent.parent / "vault" / "revenue" / "ledger.md"

_HEADER = (
    "# Revenue Ledger\n\n"
    "| date | pod | amount_usd | kind | source | external_id | note |\n"
    "|------|-----|-----------|------|--------|-------------|------|\n"
)
_VALID_KINDS = {"sale", "refund", "adjustment", "manual"}


def log_revenue(pod: str, amount_usd, source: str, external_id: str = "",
                kind: str = "sale", note: str = "") -> dict:
    """Record a real revenue event (sale/refund/adjustment/manual). Append-only;
    a correction is a reversing row with a negative amount. Dedups Stripe rows by
    external_id. Operator/CLI/dashboard only — never called autonomously by an agent."""
    try:
        amount = float(amount_usd)
    except (TypeError, ValueError):
        return {"error": f"amount_usd must be a number, got {amount_usd!r}"}
    if kind not in _VALID_KINDS:
        return {"error": f"kind must be one of {sorted(_VALID_KINDS)}"}

    result = record_revenue(pod, amount, source, external_id, kind=kind)
    if not result["recorded"]:
        return {"skipped": True, "reason": result.get("reason"), "external_id": external_id}

    REVENUE_MD.parent.mkdir(parents=True, exist_ok=True)
    if not REVENUE_MD.exists():
        REVENUE_MD.write_text(_HEADER, encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    row = f"| {today} | {pod} | {amount} | {kind} | {source} | {external_id} | {note} |\n"
    with REVENUE_MD.open("a", encoding="utf-8") as fh:
        fh.write(row)
    return {"success": True, "pod": pod, "amount_usd": amount, "kind": kind}


TOOL_SPEC = {
    "name": "log_revenue",
    "description": (
        "Record a REAL revenue event to the revenue ledger (sale, refund, adjustment, or manual "
        "entry). Append-only — a correction is a reversing row with a negative amount_usd. Stripe "
        "rows dedup by external_id. Operator-invoked only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pod": {"type": "string", "description": "Pod/product id the revenue belongs to."},
            "amount_usd": {"type": "number", "description": "USD amount; negative for a refund/reversal."},
            "source": {"type": "string", "description": "e.g. 'stripe', 'manual', 'cash'."},
            "external_id": {"type": "string", "description": "Provider txn id for dedup; blank for manual."},
            "kind": {"type": "string", "enum": ["sale", "refund", "adjustment", "manual"]},
            "note": {"type": "string", "description": "Optional human note."},
        },
        "required": ["pod", "amount_usd", "source"],
    },
}
