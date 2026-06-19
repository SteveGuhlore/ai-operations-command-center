"""export_cold_leads — hand personalized leads to the cold-email tool (never SendGrid).

Cold outreach must NOT go through SendGrid (ToS/opt-in -> suspension). This tool hands the
agent-composed, personalized leads to a dedicated cold-email platform (Instantly/Smartlead) on a
separate warmed domain — by API when configured, otherwise as a campaign-ready CSV the operator
imports. Mirrors social_dm.py (API + fallback, timeout-safe) and email_sender.py (one-export-per-
email dedup ledger). CAN-SPAM: a physical mailing address + honored opt-out are required; the cold
tool owns the unsubscribe footer, but API export is refused unless COLD_PHYSICAL_ADDRESS is set.
"""

import csv
import json
import os
import re
from datetime import date
from pathlib import Path

import httpx

_WORKSPACE = Path(__file__).parent.parent.parent / "workspace"
_VAULT = Path(__file__).parent.parent.parent / "vault"
_EXPORT_DIR = _VAULT / "outreach" / "cold-export"

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_CSV_COLS = [
    "email",
    "business",
    "first_name",
    "city",
    "business_type",
    "offer",
    "subject",
    "body",
]


def _ledger_path() -> Path:
    return Path(
        os.environ.get("COLD_EXPORTED_LOG", str(_WORKSPACE / "cold-exported.json"))
    )


def _load_ledger() -> dict:
    try:
        d = json.loads(_ledger_path().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _record_exported(emails) -> None:
    p = _ledger_path()
    log = _load_ledger()
    today = str(date.today())
    for e in emails:
        log[e.lower()] = today
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except OSError:
        pass


def _norm_leads(leads):
    """Keep valid, non-duplicate, not-already-exported leads. Returns (fresh, skipped)."""
    ledger = _load_ledger()
    seen = set()
    fresh, skipped = [], []
    for ld in leads or []:
        email = (ld.get("email") or "").strip().lower()
        if not _EMAIL_RE.match(email) or email in seen or email in ledger:
            skipped.append(ld.get("email") or ld.get("business") or "?")
            continue
        seen.add(email)
        fresh.append(ld)
    return fresh, skipped


def _write_csv(campaign: str, leads) -> Path:
    _EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9_-]+", "-", campaign.lower()).strip("-") or "trades"
    path = _EXPORT_DIR / f"{slug}-{date.today()}.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        for ld in leads:
            w.writerow({c: ld.get(c, "") for c in _CSV_COLS})
    return path


def _push_to_provider(api_url: str, api_key: str, campaign_id: str, leads) -> dict:
    payload = {
        "campaign": campaign_id,
        "leads": [
            {
                "email": l["email"],
                "company_name": l.get("business", ""),
                "first_name": l.get("first_name", ""),
                "personalization": l.get("hook", ""),
                "custom_variables": {
                    "subject": l.get("subject", ""),
                    "body": l.get("body", ""),
                    "city": l.get("city", ""),
                    "offer": l.get("offer", ""),
                },
            }
            for l in leads
        ],
    }
    try:
        r = httpx.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        if r.status_code in (200, 201, 202):
            return {"success": True}
        return {"error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as exc:
        msg = str(exc).lower()
        return {"ambiguous": "timeout" in msg or "timed out" in msg, "error": str(exc)}


def export_cold_leads(campaign: str, leads) -> dict:
    """Hand off personalized cold leads to the cold-email tool (API) or a campaign-ready CSV.
    leads: list of {email, business, subject, body, city?, business_type?, offer?, hook?, first_name?}.
    Deduped by email (one cold export per business, ever). Never uses SendGrid."""
    campaign = (campaign or "trades").strip() or "trades"
    fresh, skipped = _norm_leads(leads)
    if not fresh:
        return {
            "exported": 0,
            "skipped": len(skipped),
            "reason": "no fresh valid leads",
        }

    enabled = os.environ.get("OUTREACH_AUTOMATION", "false").lower() == "true"
    api_url = os.environ.get("COLD_EMAIL_API_URL")
    api_key = os.environ.get("COLD_EMAIL_API_KEY")
    campaign_id = os.environ.get("COLD_EMAIL_CAMPAIGN_ID", campaign)
    emails = [l["email"] for l in fresh]

    if enabled and api_url and api_key:
        if not os.environ.get("COLD_PHYSICAL_ADDRESS"):
            return {
                "error": "COLD_PHYSICAL_ADDRESS not set (CAN-SPAM) — refusing API export. "
                "Set it, or unset COLD_EMAIL_API_URL to export via CSV."
            }
        result = _push_to_provider(api_url, api_key, campaign_id, fresh)
        if result.get("success"):
            _record_exported(emails)
            return {
                "exported": len(fresh),
                "skipped": len(skipped),
                "provider": "api",
                "campaign": campaign_id,
            }
        if result.get("ambiguous"):
            # Accepted-then-timeout may have landed — log as exported so a retry can't double-add.
            _record_exported(emails)
            return {
                "warning": "API send attempted but outcome UNKNOWN; leads logged as exported to "
                "avoid a double-add. Verify in the cold tool before re-exporting.",
                "exported": len(fresh),
                "skipped": len(skipped),
            }
        # Hard failure: fall through to CSV so the composed work isn't lost.
        path = _write_csv(campaign, fresh)
        _record_exported(emails)
        return {
            "exported": len(fresh),
            "skipped": len(skipped),
            "provider": "csv-fallback",
            "csv": str(path),
            "api_error": str(result.get("error", ""))[:200],
        }

    path = _write_csv(campaign, fresh)
    _record_exported(emails)
    return {
        "exported": len(fresh),
        "skipped": len(skipped),
        "provider": "csv",
        "csv": str(path),
    }


TOOL_SPEC = {
    "name": "export_cold_leads",
    "description": (
        "Hand off personalized cold-email leads to the cold-email tool on a separate warmed domain — "
        "this is how trades-mode outreach is SENT. Do NOT use send_email for cold (SendGrid is "
        "warm/reply only). Deduped by email (one export per business, ever). When the cold tool isn't "
        "configured it writes a campaign-ready CSV to vault/outreach/cold-export/ for manual import. "
        "Give each lead a composed subject + body plus the score_and_hook 'offer'/'hook'. Example: "
        "export_cold_leads(campaign='trades-worcester', leads=[{'email':'info@acme.com',"
        "'business':'Acme Plumbing','subject':'...','body':'...','offer':'ai_receptionist'}])"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "campaign": {
                "type": "string",
                "description": "Campaign label, e.g. 'trades-worcester'.",
            },
            "leads": {
                "type": "array",
                "description": "Leads to export; each needs at least email, business, subject, body.",
                "items": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "business": {"type": "string"},
                        "first_name": {"type": "string"},
                        "city": {"type": "string"},
                        "business_type": {"type": "string"},
                        "offer": {"type": "string"},
                        "hook": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["email", "business", "subject", "body"],
                },
            },
        },
        "required": ["campaign", "leads"],
    },
}
