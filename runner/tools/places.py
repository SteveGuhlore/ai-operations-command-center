import os
import httpx

_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
_DETAIL_URL      = "https://maps.googleapis.com/maps/api/place/details/json"
_DETAIL_FIELDS   = "name,formatted_address,formatted_phone_number,website,rating,types"

TOOL_SPEC = {
    "name": "find_prospects",
    "description": (
        "Search Google Maps for local businesses by category and city. "
        "Returns name, address, phone, website (if any), and rating. "
        "Use to find businesses with no website for outreach. "
        "Falls back to instructions for web_research if no API key is set."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query":       {"type": "string",  "description": "Search query e.g. 'hair salons Boston MA' or 'plumbers Chicago IL'"},
            "max_results": {"type": "integer", "description": "Max results to return (default 10, max 15)", "default": 10},
        },
        "required": ["query"],
    },
}


def find_prospects(query: str, max_results: int = 10) -> dict:
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")

    if not api_key:
        return {
            "fallback": True,
            "message": (
                "GOOGLE_MAPS_API_KEY not set. "
                f"Use web_research with query: '{query} -inurl:yelp -site:yellowpages.com' "
                "and parse business names and addresses from the text."
            ),
        }

    max_results = min(max_results, 15)

    try:
        search_resp = httpx.get(
            _TEXT_SEARCH_URL,
            params={"query": query, "key": api_key},
            timeout=15,
        )
        search_data = search_resp.json()
        status = search_data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            return {"error": f"Places API error: {status} — {search_data.get('error_message', '')}"}

        results = []
        for place in search_data.get("results", [])[:max_results]:
            place_id = place.get("place_id")
            detail   = _get_place_detail(place_id, api_key)
            # A failed detail fetch (quota, timeout, REQUEST_DENIED) must read as UNKNOWN,
            # not "no website" — otherwise the agent pitches "I noticed you have no website"
            # to businesses that have one.
            detail_failed = detail is None
            detail = detail or {}
            results.append({
                "name":        detail.get("name") or place.get("name"),
                "address":     detail.get("formatted_address") or place.get("formatted_address"),
                "phone":       detail.get("formatted_phone_number"),
                "website":     detail.get("website"),
                "has_website": None if detail_failed else bool(detail.get("website")),
                "website_status": ("unknown — detail lookup failed, do NOT pitch as no-website"
                                   if detail_failed else "confirmed"),
                "rating":      detail.get("rating") or place.get("rating"),
                "types":       place.get("types", []),
                "place_id":    place_id,
            })

        no_site = [r for r in results if r["has_website"] is False]
        return {
            "prospects":        results,
            "no_website_count": len(no_site),
            "total_found":      len(results),
            "query":            query,
        }

    except Exception as exc:
        return {"error": str(exc)}


def _get_place_detail(place_id: str, api_key: str) -> dict | None:
    """Place detail, or None when the lookup itself failed (timeout, quota, denied) — the
    caller must treat None as 'website unknown', never as 'no website'."""
    try:
        r = httpx.get(
            _DETAIL_URL,
            params={"place_id": place_id, "fields": _DETAIL_FIELDS, "key": api_key},
            timeout=10,
        )
        data = r.json()
        if data.get("status") != "OK":
            return None
        return data.get("result", {})
    except Exception:
        return None
