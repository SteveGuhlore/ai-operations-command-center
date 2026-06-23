import os
import re
from datetime import date
from pathlib import Path
import httpx

from runner.tools.mdtable import clean_cell

BASE_DIR = Path(__file__).parent.parent.parent
DM_QUEUE = BASE_DIR / "vault" / "outreach" / "dm-queue.md"

GRAPH_API = "https://graph.facebook.com/v19.0"

# Real IG handle grammar. Rejects empty strings, URLs, and the fake handles a sloppy
# extraction can mint — those would otherwise be queued for a human to "send" to.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

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
            "instagram_handle": {
                "type": "string",
                "description": "Target Instagram handle, with or without @",
            },
            "business_name": {"type": "string", "description": "Business display name"},
            "city": {"type": "string", "description": "Business city"},
            "message": {
                "type": "string",
                "description": "DM message text (keep under 1000 chars)",
            },
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
    # Normalize: strip @, whitespace, and a pasted instagram.com/ URL prefix.
    handle = (instagram_handle or "").strip().lstrip("@")
    handle = re.sub(r"^(?:https?://)?(?:www\.)?instagram\.com/", "", handle).strip("/")
    if not _HANDLE_RE.match(handle):
        return {
            "error": f"invalid Instagram handle: {instagram_handle!r} — not queued. "
            "Mark the lead call_queued instead."
        }
    enabled = os.environ.get("OUTREACH_AUTOMATION", "false").lower() == "true"
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    page_id = os.environ.get("INSTAGRAM_PAGE_ID")

    attempted_api = False
    if enabled and token and page_id:
        result = _try_graph_dm(page_id, token, handle, message)
        if result.get("success"):
            return result
        # A timeout AFTER the API accepted the message must not silently fall through to the
        # manual queue — that's a guaranteed double-DM. Surface the ambiguity to the reviewer.
        attempted_api = (
            "timed out" in str(result.get("error", "")).lower()
            or "timeout" in str(result.get("error", "")).lower()
        )

    _queue_dm(
        business_name,
        handle,
        city,
        message,
        note="VERIFY FIRST — an API send was attempted and may have gone through"
        if attempted_api
        else "",
    )
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
                "message": {"text": message},
            },
            params={"access_token": token},
            timeout=15,
        )
        result = resp.json()
        if resp.status_code == 200 and "message_id" in result:
            return {
                "success": True,
                "handle": handle,
                "message_id": result["message_id"],
            }
        return {"error": f"Graph API {resp.status_code}: {str(result)[:200]}"}
    except Exception as exc:
        return {"error": str(exc)}


def _clean_cell(s: str) -> str:
    # pipes/newlines in any cell corrupt the markdown table a human reads to send DMs
    return clean_cell(s)


def _queue_dm(
    business_name: str, handle: str, city: str, message: str, note: str = ""
) -> None:
    today = date.today().isoformat()
    if not DM_QUEUE.exists():
        DM_QUEUE.parent.mkdir(parents=True, exist_ok=True)
        DM_QUEUE.write_text(
            "# Instagram DM Queue\n\n| Business | Handle | City | Message | Date |\n|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    short_msg = _clean_cell(message)[:80] + ("…" if len(message) > 80 else "")
    if note:
        short_msg = f"⚠️ {note} — {short_msg}"
    row = f"| {_clean_cell(business_name)} | @{_clean_cell(handle)} | {_clean_cell(city)} | {short_msg} | {today} |\n"
    with DM_QUEUE.open("a", encoding="utf-8") as f:
        f.write(row)
