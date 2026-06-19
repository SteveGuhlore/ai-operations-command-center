import os

import httpx

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
# Places API (New) field mask — Enterprise tier. Deliberately excludes places.reviews (the review
# TEXTS are unused and would bump this to the pricier Atmosphere tier); rating + userRatingCount are
# what the lead_score review-hook needs.
_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
    "places.websiteUri,places.rating,places.userRatingCount,places.types"
)

TOOL_SPEC = {
    "name": "find_prospects",
    "description": (
        "Search Google Maps (Places API) for local businesses by category and city. "
        "Returns name, address, phone, website (if any), rating, and review count. "
        "Use to find businesses for outreach. "
        "Falls back to instructions for web_research if no API key is set."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query e.g. 'hair salons Boston MA' or 'plumbers Chicago IL'",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results to return (default 10, max 20)",
                "default": 10,
            },
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

    max_results = min(max_results, 20)  # Places API (New) searchText hard cap

    try:
        resp = httpx.post(
            _SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": _FIELD_MASK,
            },
            json={"textQuery": query, "maxResultCount": max_results},
            timeout=15,
        )
        if resp.status_code != 200:
            try:
                msg = resp.json().get("error", {}).get("message", "")
            except Exception:
                msg = resp.text[:200]
            return {"error": f"Places API (New) {resp.status_code}: {msg}"}

        results = []
        # One authoritative call: websiteUri is present iff the business has a site, so has_website is
        # a clean 2-state (no separate detail call that could fail and force an "unknown").
        for pl in (resp.json().get("places") or [])[:max_results]:
            website = pl.get("websiteUri")
            results.append(
                {
                    "name": (pl.get("displayName") or {}).get("text"),
                    "address": pl.get("formattedAddress"),
                    "phone": pl.get("nationalPhoneNumber"),
                    "website": website,
                    "has_website": bool(website),
                    "website_status": "confirmed",
                    "rating": pl.get("rating"),
                    "user_ratings_total": pl.get("userRatingCount"),
                    "reviews": [],
                    "types": pl.get("types", []),
                    "place_id": pl.get("id"),
                }
            )

        no_site = [r for r in results if r["has_website"] is False]
        return {
            "prospects": results,
            "no_website_count": len(no_site),
            "total_found": len(results),
            "query": query,
        }

    except Exception as exc:
        return {"error": str(exc)}
