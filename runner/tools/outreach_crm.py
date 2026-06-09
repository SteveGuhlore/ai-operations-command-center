"""log_outreach_lead — deterministic CRM persistence for the outreach pod.

The outreach_worker was told to hand-write pipe-delimited rows into
vault/outreach/crm.md via file_editor(action=append). In practice it narrated the
append without reliably emitting a correctly-formatted row, so the CRM stayed
empty while the dashboard, synthesis, and revenue rollup all read 0. This tool
removes the formatting/persistence burden from the LLM: it takes the lead fields
and writes one canonical, append-only row (creating the file + header if missing),
deduped by business name. The agent supplies data, not markdown.
"""
import logging
import os
from datetime import date
from pathlib import Path

_log = logging.getLogger(__name__)

CRM_FILE = Path(os.environ.get(
    "OUTREACH_CRM_FILE",
    str(Path(__file__).parent.parent.parent / "vault" / "outreach" / "crm.md"),
))

HEADER = "| Business | Type | City | Contact | Channel | Status | Date | Notes |"
DIVIDER = "|----------|------|------|---------|---------|--------|------|-------|"

_VALID_STATUS = {
    "email_sent", "dm_queued", "call_queued",
    "replied", "closed", "no_interest", "followed_up",
}


def _existing_names() -> set[str]:
    if not CRM_FILE.exists():
        return set()
    names: set[str] = set()
    for line in CRM_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Business" in line[:30]:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if parts and parts[0]:
            names.add(parts[0].lower())
    return names


def _clean(value: str) -> str:
    # Pipes would break the row; collapse them so a stray one can't corrupt the table.
    return (value or "").replace("|", "/").replace("\n", " ").strip()


def log_outreach_lead(
    business: str,
    business_type: str = "",
    city: str = "",
    contact: str = "",
    channel: str = "",
    status: str = "call_queued",
    notes: str = "",
) -> dict:
    """Append one prospect to the outreach CRM. Dedupes by business name (skips if already
    present). Creates the file + header on first write. Append-only by construction — it can
    never overwrite existing rows."""
    business = _clean(business)
    if not business:
        return {"error": "business name is required"}

    status = (status or "call_queued").strip().lower()
    if status not in _VALID_STATUS:
        return {"error": f"invalid status '{status}'", "valid": sorted(_VALID_STATUS)}

    if business.lower() in _existing_names():
        return {"skipped": "duplicate", "business": business}

    row = "| " + " | ".join([
        business,
        _clean(business_type),
        _clean(city),
        _clean(contact) or "—",
        _clean(channel),
        status,
        str(date.today()),
        _clean(notes),
    ]) + " |"

    try:
        CRM_FILE.parent.mkdir(parents=True, exist_ok=True)
        new_file = not CRM_FILE.exists() or CRM_FILE.stat().st_size == 0
        with CRM_FILE.open("a", encoding="utf-8") as f:
            if new_file:
                f.write(HEADER + "\n" + DIVIDER + "\n")
            f.write(row + "\n")
        return {"success": True, "business": business, "status": status}
    except OSError as exc:
        _log.warning("log_outreach_lead failed: %s", exc)
        return {"error": str(exc)}


TOOL_SPEC = {
    "name": "log_outreach_lead",
    "description": (
        "Persist ONE prospect to the Easy Simple Sites outreach CRM — call this once per "
        "business you process, instead of hand-writing a markdown row. It formats and appends "
        "the row for you (append-only, deduped by business name, creates the file if needed), so "
        "the dashboard and revenue rollup see the lead. ALWAYS call this for every prospect; "
        "narrating that you added a lead without calling this tool means it was NOT saved. "
        "Example: log_outreach_lead(business='Texture Salon', business_type='Hair Salon', "
        "city='Salem, MA', contact='hello@texturesalon.com', channel='email', status='email_sent')"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "business": {"type": "string", "description": "Business name (required)."},
            "business_type": {"type": "string", "description": "Category, e.g. 'Hair Salon', 'Plumber', 'Daycare'."},
            "city": {"type": "string", "description": "City and state, e.g. 'Salem, MA'."},
            "contact": {"type": "string", "description": "Email, IG handle, or phone if known; leave blank if none."},
            "channel": {"type": "string", "description": "How you reached out: 'email', 'instagram', or 'phone'."},
            "status": {
                "type": "string",
                "description": (
                    "email_sent = emailed. dm_queued = IG DM sent/queued. call_queued = phone-only, "
                    "not yet contacted. Only use replied/closed/no_interest after a real human reply."
                ),
                "enum": ["email_sent", "dm_queued", "call_queued", "replied", "closed", "no_interest", "followed_up"],
            },
            "notes": {"type": "string", "description": "Optional short note."},
        },
        "required": ["business", "status"],
    },
}
