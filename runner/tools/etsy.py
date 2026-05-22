import os
import httpx

ETSY_API_BASE = "https://openapi.etsy.com/v3/application"


def create_draft_listing(
    title: str,
    description: str,
    price: float,
    tags: list[str],
    quantity: int = 999,
    taxonomy_id: int = 2078,
    who_made: str = "i_did",
    when_made: str = "made_to_order",
    is_digital: bool = True,
) -> dict:
    api_key = os.environ.get("ETSY_API_KEY")
    shop_id = os.environ.get("ETSY_SHOP_ID")

    if not api_key or not shop_id:
        return {"error": "ETSY_API_KEY and ETSY_SHOP_ID must be set in .env"}

    payload = {
        "title": title[:140],
        "description": description,
        "price": round(price, 2),
        "quantity": quantity,
        "tags": tags[:13],
        "taxonomy_id": taxonomy_id,
        "who_made": who_made,
        "when_made": when_made,
        "is_digital": is_digital,
        "state": "draft",
    }

    try:
        response = httpx.post(
            f"{ETSY_API_BASE}/shops/{shop_id}/listings",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        data = response.json()
        if response.status_code == 201:
            return {
                "success": True,
                "listing_id": data.get("listing_id"),
                "state": data.get("state"),
                "url": data.get("url", ""),
                "title": title,
            }
        return {"error": data.get("error", f"HTTP {response.status_code}"), "status_code": response.status_code}
    except Exception as exc:
        return {"error": str(exc)}


def etsy_listing(
    title: str,
    description: str,
    price: float,
    tags: list[str],
    quantity: int = 999,
) -> dict:
    return create_draft_listing(title, description, price, tags, quantity)


TOOL_SPEC = {
    "name": "etsy_listing",
    "description": "Create a draft Etsy listing. Requires ETSY_API_KEY and ETSY_SHOP_ID in environment. Listings are created as drafts — not live until Level 3 is enabled.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Listing title (max 140 chars)"},
            "description": {"type": "string", "description": "Full listing description"},
            "price": {"type": "number", "description": "Price in USD"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 13 tags",
            },
            "quantity": {"type": "integer", "default": 999, "description": "Quantity available"},
        },
        "required": ["title", "description", "price", "tags"],
    }
}
