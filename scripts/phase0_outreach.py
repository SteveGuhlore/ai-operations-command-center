"""Phase-0 outreach validation runner — DETERMINISTIC (no LLM agent).

Calls the funnel tools directly (find_prospects -> score_and_hook -> enrich_site_contacts ->
export_cold_leads -> log_outreach_lead) with templated per-offer copy, so a Phase-0 batch reliably
produces a CSV for manual validation at ~$0 LLM cost. (The agent-based path skipped steps and cost
$0.57; for validation we want determinism, not orchestration by a weak model.)

A live run spends only Places + Apify (pod-capped). --dry-run makes zero calls and previews the copy.
Needs in .env: GOOGLE_MAPS_API_KEY (discovery); APIFY_TOKEN + APIFY_CONTACT_ACTOR (emails). Keep
OUTREACH_AUTOMATION unset/false for Phase 0 (export goes to CSV).

Usage:
    python scripts/phase0_outreach.py --city "Worcester, MA" --category plumbers --max 10
    python scripts/phase0_outreach.py --city "Lowell, MA" --category HVAC --dry-run
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from runner.ledger.budget import is_pod_budget_exceeded
from runner.tools.apify import enrich_site_contacts
from runner.tools.cold_export import export_cold_leads
from runner.tools.lead_score import score_and_hook
from runner.tools.outreach_crm import log_outreach_lead
from runner.tools.places import find_prospects

POD = "local_outreach_pod"

_GENERIC = {
    "ai_receptionist": "most home-services calls that hit voicemail never get a callback",
    "review_automation": "steady new Google reviews are the cheapest way to climb local search",
    "site_care": "most customers check for a website before they call",
}


def _compose(offer: str, business: str, category: str, hook: str) -> tuple[str, str]:
    """Deterministic per-offer copy. Opens with the real hook (or a generic line), no fabricated claims."""
    booking = os.environ.get("COLD_BOOKING_URL", "").strip()
    cta = (
        f"Worth a quick 15-min look? {booking}"
        if booking
        else "Open to a quick 15-min look?"
    )
    opener = (
        f"Noticed {hook}."
        if hook
        else _GENERIC.get(offer, _GENERIC["review_automation"]).capitalize() + "."
    )
    sig = (
        "\n\n— Stephen, easysimplesites.org\n\nReply STOP and I won't reach out again."
    )
    if offer == "ai_receptionist":
        subject = f"{business} — missed calls = missed jobs?"
        pitch = (
            "We set up an AI receptionist + missed-call text-back so a missed call becomes a booked "
            "job instead of a voicemail nobody returns. Runs 24/7, ~$299/mo."
        )
    elif offer == "site_care":
        subject = f"{business} — a simple website"
        pitch = (
            f"We build a clean, mobile-friendly site for local {category} — $299 one-time, you own "
            "it, no monthly fees."
        )
    else:  # review_automation
        subject = f"{business} — more Google reviews"
        pitch = (
            "We run done-for-you Google review requests (compliant — we never filter reviews) so you "
            "steadily climb local search. ~$149/mo."
        )
    return subject, f"Hi {business},\n\n{opener}\n\n{pitch}\n\n{cta}{sig}"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Deterministic Phase-0 outreach batch (CSV, no live send)."
    )
    ap.add_argument("--city", required=True, help='City + state, e.g. "Worcester, MA"')
    ap.add_argument(
        "--category", required=True, help="Trade category, e.g. plumbers, HVAC, roofers"
    )
    ap.add_argument("--max", type=int, default=10, help="Max prospects (default 10)")
    ap.add_argument(
        "--campaign", default="", help="Campaign label (default derived from the city)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Preview copy; make zero API calls"
    )
    args = ap.parse_args()

    campaign = args.campaign or "trades-" + re.sub(
        r"[^a-z0-9]+", "-", args.city.lower()
    ).strip("-")
    print(f"\n{'=' * 60}\n  Phase-0 (deterministic)  |  {args.category} in {args.city}")
    print(f"  campaign '{campaign}'  (max {args.max})\n{'=' * 60}")

    if args.dry_run:
        print("\nDRY RUN — no API calls. Sample copy per offer:")
        for offer in ("ai_receptionist", "review_automation", "site_care"):
            s, b = _compose(
                offer,
                "Acme Plumbing",
                args.category,
                "you're at 4.6 stars across 80 reviews",
            )
            print(f"\n[{offer}] subject: {s}\n{b}")
        print(
            "\nReal run: find_prospects -> score_and_hook -> enrich_contacts -> export_cold_leads(CSV) -> log_outreach_lead"
        )
        return

    if is_pod_budget_exceeded(POD):
        print(f"ABORT: {POD} is over its daily spend cap (config/budgets.yaml).")
        sys.exit(1)

    res = find_prospects(f"{args.category} {args.city}", args.max)
    if res.get("error"):
        print(f"find_prospects error: {res['error']}")
        sys.exit(1)
    if res.get("fallback"):
        print(
            f"find_prospects fell back (GOOGLE_MAPS_API_KEY missing/invalid?): {res.get('message')}"
        )
        sys.exit(1)
    prospects = res.get("prospects", [])
    print(
        f"\nfound {len(prospects)} prospects ({res.get('no_website_count', 0)} without a website)"
    )
    if not prospects:
        return

    for p in prospects:
        sh = score_and_hook(
            p.get("name", ""),
            args.category,
            args.city,
            p.get("rating"),
            p.get("user_ratings_total"),
            p.get("has_website"),
            p.get("types"),
        )
        p["_offer"], p["_hook"], p["_tier"] = sh["offer"], sh["hook"], sh["tier"]

    sites = [
        p["website"] for p in prospects if p.get("has_website") and p.get("website")
    ]
    contacts: dict = {}
    if sites:
        en = enrich_site_contacts(sites)
        if en.get("contacts"):
            contacts = en["contacts"]
        elif en.get("fallback"):
            print(
                f"enrich fell back (APIFY_TOKEN missing?) — emails will be sparse: {en.get('message')}"
            )
        elif en.get("error"):
            print(f"enrich error: {en['error']}")

    leads, by_offer, emailable = [], {}, 0
    for p in prospects:
        by_offer[p["_offer"]] = by_offer.get(p["_offer"], 0) + 1
        email = (contacts.get(p.get("website") or "", {}).get("emails") or [None])[0]
        note = f"{p['_offer']} | {p['_tier']}"
        if email:
            emailable += 1
            subject, body = _compose(p["_offer"], p["name"], args.category, p["_hook"])
            leads.append(
                {
                    "email": email,
                    "business": p["name"],
                    "business_type": args.category,
                    "city": args.city,
                    "offer": p["_offer"],
                    "hook": p["_hook"],
                    "subject": subject,
                    "body": body,
                }
            )
            log_outreach_lead(
                business=p["name"],
                business_type=args.category,
                city=args.city,
                contact=email,
                channel="email",
                status="cold_export",
                notes=note,
            )
        else:
            log_outreach_lead(
                business=p["name"],
                business_type=args.category,
                city=args.city,
                contact=p.get("phone") or "",
                channel="phone",
                status="call_queued",
                notes=note,
            )

    exp = (
        export_cold_leads(campaign, leads)
        if leads
        else {"exported": 0, "reason": "no emails found"}
    )
    print(f"\nby offer: {by_offer}")
    print(f"emailable: {emailable}/{len(prospects)}   export: {exp}")
    print("CSV -> vault/outreach/cold-export/   |   CRM -> vault/outreach/crm.md")


if __name__ == "__main__":
    main()
