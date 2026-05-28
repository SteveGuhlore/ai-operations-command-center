import os
from datetime import date
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).parent.parent.parent
DM_QUEUE = BASE_DIR / "vault" / "outreach" / "dm-queue.md"

GRAPH_API = "https://graph.facebook.com/v19.0"

TOOL_SPEC = {
    "name": "send_instagram_dm",
    "description": (
        "Send an Instagram DM to a business prospect. "
        "Uses the Instagram Graph API if credentials are present. "
        "Falls back to logging to vault/outreach/dm-queue.md for manual sending. "
        "Note: Instagram Graph API DMs require the recipient to have previously messaged your page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "instagram_handle": {"type": "string", "description": "Target Instagram handle, with or without @"},
            "business_name":    {"type": "string", "description": "Business display name"},
            "city":             {"type": "string", "description": "Business city"},
            "message":          {"type": "string", "description": "DM message text (keep under 1000 chars)"},
        },
        "required": ["instagram_handle", "business_name", "message"],
    },
}


def send_instagram_dm(
    instagram_handle: str,
    business_name: str,
    message: str,
    city: str = "",
) -> dict:
    handle  = instagram_handle.lstrip("@")
    enabled = os.environ.get("OUTREACH_AUTOMATION", "false").lower() == "true"
    token   = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    page_id = os.environ.get("INSTAGRAM_PAGE_ID")

    if enabled and token and page_id:
        result = _try_graph_dm(page_id, token, handle, message)
        if result.get("success"):
            return result

    _queue_dm(business_name, handle, city, message)
    return {
        "queued": True,
        "handle": handle,
        "reason": (
            "DM queued in vault/outreach/dm-queue.md. "
            "Instagram Graph API DMs require prior contact from the recipient. "
            "Review the queue for manual or browser-automation sending."
        ),
    }


def _try_graph_dm(page_id: str, token: str, handle: str, message: str) -> dict:
    try:
        search = httpx.get(
            f"{GRAPH_API}/ig_messaging_guest_search",
            params={"username": handle, "access_token": token},
            timeout=10,
        )
        data = search.json()
        if "error" in data or not data.get("data"):
            return {"error": "Recipient not reachable via Graph API"}

        recipient_id = data["data"][0].get("id")
        if not recipient_id:
            return {"error": "No recipient ID found"}

        resp = httpx.post(
            f"{GRAPH_API}/{page_id}/messages",
            json={
                "recipient": {"id": recipient_id},
                "message":   {"text": message},
            },
            params={"access_token": token},
            timeout=15,
        )
        result = resp.json()
        if resp.status_code == 200 and "message_id" in result:
            return {"success": True, "handle": handle, "message_id": result["message_id"]}
        return {"error": f"Graph API {resp.status_code}: {str(result)[:200]}"}
    except Exception as exc:
        return {"error": str(exc)}


def _queue_dm(business_name: str, handle: str, city: str, message: str) -> None:
    today = date.today().isoformat()
    if not DM_QUEUE.exists():
        DM_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        DM_QUEUE.write_text(
            "# Instagram DM Queue\n\n| Business | Handle | City | Message | Date |\n|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    short_msg = message[:80].replace("|", "/") + ("…" if len(message) > 80 else "")
    row = f"| {business_name} | @{handle} | {city} | {short_msg} | {today} |\n"
    with DM_QUEUE.open("a", encoding="utf-8") as f:
        f.write(row)
