"""score_and_hook — deterministic prospect scoring + offer routing for the trades funnel.

The outreach_worker needs to (a) prioritize prospects and (b) pick the RIGHT offer + opening
line per business, without the LLM inventing social proof. This tool maps the signals the
lead-engine already has (Google rating, review count, website presence) to a recommended offer
and a personalization hook built ONLY from the prospect's real numbers. Mirrors the
deterministic-formatter contract of outreach_crm.py: the agent supplies fields, the tool returns
the canonical routing + hook.

Offer routing (Places-only signals today; richer signals like online-booking come from enrichment):
  no website                  -> site_care        (easy-simple-sites + care plan)
  website, busy (many reviews) -> ai_receptionist  (missed-call-text-back; flagship)
  website, few reviews         -> review_automation (compliant review generation, never gating)

No hook is emitted below REVIEW_FLOOR so we never fabricate or overstate social proof.
"""

# Trades beachhead — home services. Matched against business_type + Google place types.
_TRADES = {
    "plumber",
    "plumbing",
    "hvac",
    "heating",
    "air conditioning",
    "electrician",
    "electrical",
    "roofer",
    "roofing",
    "landscaper",
    "landscaping",
    "general contractor",
    "contractor",
    "garage door",
    "pest control",
    "painter",
    "painting",
    "flooring",
    "remodel",
    "handyman",
    "fencing",
    "concrete",
    "septic",
    "chimney",
    "gutter",
    "locksmith",
    "pool",
    "tree service",
    "paving",
    "excavation",
}

REVIEW_FLOOR = 5  # below this, review count is too thin to cite as social proof
BUSY_REVIEWS = (
    75  # at/above this the "slammed -> missed calls" receptionist pitch is credible
)


def _is_trades(business_type: str, types) -> bool:
    blob = (business_type or "").lower() + " " + " ".join(types or []).lower()
    return any(t in blob for t in _TRADES)


def _fmt_rating(rating) -> str:
    try:
        return f"{float(rating):.1f}"
    except (TypeError, ValueError):
        return ""


def score_and_hook(
    business: str,
    business_type: str = "",
    city: str = "",
    rating=None,
    user_ratings_total=None,
    has_website=None,
    types=None,
) -> dict:
    """Rank a prospect and pick its offer + opening hook. Deterministic; uses only real data.

    Returns {score 0-100, tier, offer, hook, fit_reason}. `hook` is empty when there isn't enough
    real signal to personalize honestly — the agent must NOT invent ratings/reviews.
    """
    trades = _is_trades(business_type, types)
    try:
        reviews_n = int(user_ratings_total) if user_ratings_total is not None else None
    except (TypeError, ValueError):
        reviews_n = None
    rating_s = _fmt_rating(rating)

    # --- offer routing -----------------------------------------------------
    if has_website is False:
        offer = "site_care"
    elif reviews_n is not None and reviews_n >= BUSY_REVIEWS:
        offer = "ai_receptionist"
    else:
        offer = "review_automation"

    # --- personalization hook (real data only) -----------------------------
    hook = ""
    if offer == "site_care":
        hook = "your business doesn't have a mobile-friendly website — and most local searches happen on a phone"
    elif reviews_n is not None and reviews_n >= REVIEW_FLOOR and rating_s:
        if offer == "ai_receptionist":
            hook = (
                f"you're at {rating_s} stars across {reviews_n} reviews — clearly busy; the real "
                "question is how many calls go to voicemail"
            )
        else:
            hook = (
                f"you're at {rating_s} stars with {reviews_n} reviews — a steady stream of new "
                "reviews would push you up in local search"
            )

    # --- score -------------------------------------------------------------
    score = 0
    fit = []
    if trades:
        score += 40
        fit.append("trades")
    else:
        fit.append("non-trades")
    if has_website is True:
        score += 25
        fit.append("has-site")
    elif has_website is None:
        score += 5
        fit.append("site-unknown")
    else:
        fit.append("no-site")
    if reviews_n is not None:
        if reviews_n >= BUSY_REVIEWS:
            score += 25
            fit.append("busy")
        elif reviews_n >= REVIEW_FLOOR:
            score += 15
            fit.append("reviewed")
        elif reviews_n >= 1:
            score += 5
            fit.append("few-reviews")
    if rating_s:
        score += 10
    score = min(score, 100)
    tier = "high" if score >= 70 else "medium" if score >= 45 else "low"

    return {
        "business": business,
        "score": score,
        "tier": tier,
        "offer": offer,
        "hook": hook,
        "fit_reason": ", ".join(fit),
    }


TOOL_SPEC = {
    "name": "score_and_hook",
    "description": (
        "Score a trades prospect and pick the RIGHT offer + opening line from its real Google "
        "signals (rating, review count, website). Call once per prospect before composing. Returns "
        "score/tier, the recommended offer (ai_receptionist | review_automation | site_care), and a "
        "'hook' string. Use the hook VERBATIM and never invent ratings or review counts — an empty "
        "hook means there isn't enough real data to personalize, so open generically. Example: "
        "score_and_hook(business='Acme Plumbing', business_type='Plumber', city='Worcester, MA', "
        "rating=4.8, user_ratings_total=126, has_website=True)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "business": {"type": "string", "description": "Business name (required)."},
            "business_type": {
                "type": "string",
                "description": "Category, e.g. 'Plumber', 'HVAC', 'Roofer'.",
            },
            "city": {
                "type": "string",
                "description": "City and state, e.g. 'Worcester, MA'.",
            },
            "rating": {
                "type": "number",
                "description": "Google star rating, if known.",
            },
            "user_ratings_total": {
                "type": "integer",
                "description": "Google review count, if known.",
            },
            "has_website": {
                "type": "boolean",
                "description": "True/False from find_prospects; omit if unknown.",
            },
            "types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Google place types, if available.",
            },
        },
        "required": ["business"],
    },
}
