import os
import httpx

SENDGRID_API = "https://api.sendgrid.com/v3/mail/send"

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


def send_email(to_email: str, to_name: str, subject: str, body: str) -> dict:
    api_key    = os.environ.get("SENDGRID_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "outreach@easysimplesites.org")
    from_name  = os.environ.get("FROM_NAME", "Stephen")
    enabled    = os.environ.get("OUTREACH_AUTOMATION", "false").lower() == "true"

    if not api_key:
        return {"queued": True, "reason": "SENDGRID_API_KEY not set — email staged for review"}

    if not enabled:
        return {"queued": True, "reason": "OUTREACH_AUTOMATION not enabled — email staged for review"}

    if "STOP" not in body and "unsubscribe" not in body.lower():
        return {"error": "Email body must include an unsubscribe instruction (CAN-SPAM required)"}

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
            return {"success": True, "to": to_email, "subject": subject}
        return {"error": f"SendGrid {r.status_code}: {r.text[:300]}"}
    except Exception as exc:
        return {"error": str(exc)}
