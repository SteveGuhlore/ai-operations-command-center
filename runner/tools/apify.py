"""enrich_site_contacts — reliable contact enrichment via our own Apify actor.

The outreach_worker's old contact lookup (web_research) is disabled by prompt rule #4 because it
CAPTCHAs and burns the step budget. This tool calls our own `site-contact-extractor` actor on a
batch of business websites and returns contacts in the SAME structured shape web.py emits, so the
agent's email->IG->call decision logic is unchanged. Spend is metered against local_outreach_pod
and refused when the pod is over its daily cap.
"""

import logging
import os

import httpx

from runner.ledger.budget import is_pod_budget_exceeded, record_spend

_log = logging.getLogger(__name__)

_POD = "local_outreach_pod"
_ATTRIB_ROLE = (
    "outreach_worker"  # spend attribution — tools have no role_id of their own
)
# Actor lives in our own Apify account (mirrors arb-bot's actors). Override per deploy.
_ACTOR = os.environ.get("APIFY_CONTACT_ACTOR", "local-outreach~site-contact-extractor")
_MAX_URLS = 25  # bound a single call so one agent step can't fan out unbounded
# Conservative per-URL cost estimate (compute + proxy). Reconcile with the actor's real run cost
# [CONFIRM arb-bot]; the pod cap is the hard backstop regardless of the estimate.
_COST_PER_URL = float(os.environ.get("APIFY_COST_PER_URL", "0.003"))


def _map_item(item: dict) -> dict:
    """Apify dataset item -> the exact shape web.py::_extract_business_contact_info returns."""
    return {
        "emails": list(item.get("emails") or []),
        "phones": list(item.get("phones") or []),
        "instagram_handles": list(item.get("instagram_handles") or []),
        "facebook_pages": list(item.get("facebook_pages") or []),
        "linkedin_profiles": list(item.get("linkedin_profiles") or []),
        "raw_text": (item.get("raw_text") or "")[:2000],
    }


def enrich_site_contacts(urls) -> dict:
    """Enrich business websites with contact info via our Apify actor. Pass the websites from
    find_prospects; returns {contacts: {url: {emails, phones, instagram_handles, facebook_pages,
    linkedin_profiles, raw_text}}, count, provider}. Preferred over web_research for contact lookup.
    """
    if isinstance(urls, str):
        urls = [urls]
    urls = [u for u in (urls or []) if u][:_MAX_URLS]
    if not urls:
        return {"contacts": {}, "count": 0, "provider": "apify"}

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return {
            "fallback": True,
            "message": (
                "APIFY_TOKEN not set. Skip enrichment and fall back to the prospect's Google "
                "phone (call_queued); do NOT use web_research for contact lookup."
            ),
        }

    if is_pod_budget_exceeded(_POD):
        return {
            "error": f"{_POD} daily budget exceeded — enrichment paused",
            "contacts": {},
        }

    try:
        resp = httpx.post(
            f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items",
            params={"token": token},
            json={"urls": urls, "maxPagesPerSite": 3, "respectRobots": True},
            timeout=120,
        )
        if resp.status_code not in (200, 201):
            return {
                "error": f"Apify {resp.status_code}: {resp.text[:200]}",
                "contacts": {},
            }
        items = resp.json() or []
    except Exception as exc:
        _log.warning("enrich_site_contacts failed: %s", exc)
        return {"error": str(exc), "contacts": {}}

    record_spend(_ATTRIB_ROLE, len(urls) * _COST_PER_URL, pod=_POD)

    contacts = {}
    for item in items:
        url = item.get("url")
        if url:
            contacts[url] = _map_item(item)
    return {"contacts": contacts, "count": len(contacts), "provider": "apify"}


TOOL_SPEC = {
    "name": "enrich_contacts",
    "description": (
        "PREFERRED contact-lookup tool: given the websites from find_prospects, returns each "
        "business's emails, phones, and social handles (same fields as web_research, but reliable — "
        "use this instead of web_research for contact lookup). Pass all prospect websites at once. "
        "Returns {contacts: {url: {emails, phones, instagram_handles, facebook_pages, "
        "linkedin_profiles, raw_text}}}. If a business has no website there's nothing to enrich — "
        "use its Google phone for call_queued. Example: enrich_contacts(urls=['https://acme.com'])"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Business website URLs (from the find_prospects 'website' field).",
            },
        },
        "required": ["urls"],
    },
}
