import json
import os
import re
from datetime import date
from pathlib import Path

import httpx

SENDGRID_API = "https://api.sendgrid.com/v3/mail/send"

_WORKSPACE = Path(__file__).parent.parent.parent / "workspace"
_VAULT = Path(__file__).parent.parent.parent / "vault"

# RFC-lite: enough to reject empty/garbage/"Name <a@b>" shapes the agent might pass through.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# An address whose "domain" is an asset filename (hero@1x.png) — never a real mailbox.
_ASSET_DOMAIN_RE = re.compile(r"\.(?:png|jpe?g|gif|webp|svg|css|js|ico|woff2?|ttf)$", re.IGNORECASE)

TOOL_SPEC = {
    "name": "send_email",
    "description": (
        "Send a cold outreach email via SendGrid to a local business prospect. "
        "Only use for businesses confirmed to have no existing website. "
        "Requires SENDGRID_API_KEY and OUTREACH_AUTOMATION=true in environment."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "to_email": {"type": "string", "description": "Recipient email address"},
            "to_name":  {"type": "string", "description": "Recipient business name"},
            "subject":  {"type": "string", "description": "Email subject line"},
            "body":     {"type": "string", "description": "Plain text email body (must include unsubscribe line at the bottom)"},
        },
        "required": ["to_email", "to_name", "subject", "body"],
    },
}


def _sent_log_path() -> Path:
    return Path(os.environ.get("OUTREACH_SENT_LOG", str(_WORKSPACE / "outreach-sent.json")))


def _review_queue_path() -> Path:
    return Path(os.environ.get("OUTREACH_EMAIL_QUEUE", str(_VAULT / "outreach" / "email-queue.md")))


def _already_sent(to_email: str) -> bool:
    try:
        log = json.loads(_sent_log_path().read_text(encoding="utf-8"))
        return to_email.lower() in log
    except (OSError, json.JSONDecodeError):
        return False


def _record_sent(to_email: str) -> None:
    p = _sent_log_path()
    try:
        log = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(log, dict):
            log = {}
    except (OSError, json.JSONDecodeError):
        log = {}
    log[to_email.lower()] = str(date.today())
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except OSError:
        pass


def _stage_for_review(to_email: str, to_name: str, subject: str, body: str, reason: str) -> dict:
    """Persist the full email to a human-review queue. The old behavior claimed 'staged for
    review' while writing NOTHING — the pitch vanished, yet the agent logged the lead as
    contacted (success-shaped return, per its prompt). Now staged means actually staged."""
    q = _review_queue_path()
    try:
        q.parent.mkdir(parents=True, exist_ok=True)
        with q.open("a", encoding="utf-8") as f:
            f.write(f"\n## {date.today()} — {to_name} <{to_email}>\n"
                    f"**Why staged:** {reason}\n\n"
                    f"**Subject:** {subject}\n\n{body}\n\n---\n")
        return {"queued": True, "sent": False, "queue_file": str(q),
                "reason": f"{reason} — email written to review queue, NOT sent"}
    except OSError as exc:
        return {"error": f"{reason}; staging to review queue also failed: {exc}"}


def send_email(to_email: str, to_name: str, subject: str, body: str) -> dict:
    api_key    = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "outreach@easysimplesites.org")
    from_name  = os.environ.get("FROM_NAME", "Stephen")
    enabled    = os.environ.get("OUTREACH_AUTOMATION", "false").lower() == "true"

    to_email = (to_email or "").strip()
    if not _EMAIL_RE.match(to_email) or _ASSET_DOMAIN_RE.search(to_email.split("@", 1)[-1]):
        return {"error": f"invalid recipient address: {to_email!r} — not sent. "
                         "Mark the lead call_queued instead of emailing a garbage address."}

    if "STOP" not in body and "unsubscribe" not in body.lower():
        return {"error": "Email body must include an unsubscribe instruction (CAN-SPAM required)"}

    # One cold email per recipient, ever — a timeout-then-retry or a re-run must not
    # double-contact a real business.
    if _already_sent(to_email):
        return {"error": f"{to_email} was already emailed (see outreach-sent log) — not re-sent. "
                         "Treat this lead as contacted."}

    if not api_key:
        return _stage_for_review(to_email, to_name, subject, body, "SENDGRID_API_KEY not set")

    if not enabled:
        return _stage_for_review(to_email, to_name, subject, body, "OUTREACH_AUTOMATION not enabled")

    payload = {
        "personalizations": [{"to": [{"email": to_email, "name": to_name}]}],
        "from": {"email": from_email, "name": from_name},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }

    try:
        r = httpx.post(
            SENDGRID_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        if r.status_code in (200, 202):
            _record_sent(to_email)
            return {"success": True, "to": to_email, "subject": subject}
        return {"error": f"SendGrid {r.status_code}: {r.text[:300]}"}
    except Exception as exc:
        # The request may have been accepted before the connection dropped — record it so a
        # retry can't double-send, and say so explicitly.
        _record_sent(to_email)
        return {"error": f"{exc} — send outcome UNKNOWN; recipient logged as contacted to "
                         "prevent a double-send. Do not retry this address."}
