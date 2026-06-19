"""Phase-0 outreach validation runner.

Runs the outreach_worker ONCE against a generated trades-acquisition task for a single city +
category, producing a campaign CSV in vault/outreach/cold-export/ (CSV mode — no live send) plus
CRM rows, so the operator can validate messaging before automating. Unlike scripts/test_agent.py
this does not hard-require ANTHROPIC_API_KEY (the outreach role runs on gemini) and it builds the
task in-memory. A live run makes real (pod-capped) LLM/Places/Apify spend; --dry-run makes none.

Live run needs in .env: GOOGLE_AI_API_KEY (gemini), GOOGLE_MAPS_API_KEY (Places),
APIFY_TOKEN + APIFY_CONTACT_ACTOR (enrichment). Keep OUTREACH_AUTOMATION unset/false for Phase 0.

Usage:
    python scripts/phase0_outreach.py --city "Worcester, MA" --category plumbers
    python scripts/phase0_outreach.py --city "Lowell, MA" --category HVAC --max 15 --campaign trades-lowell
    python scripts/phase0_outreach.py --city "Salem, MA" --category roofers --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.ledger.budget import is_pod_budget_exceeded
from runner.main import MODELS, ROLE_TOOLS

ROLE = "outreach_worker"
POD = "local_outreach_pod"


def _body(city: str, category: str, max_results: int, campaign: str) -> str:
    return f"""Trades acquisition — PHASE 0 VALIDATION. No live send (OUTREACH_AUTOMATION is off); export to CSV only.

City: {city}
Category: {category}
Target: up to {max_results} prospects.

Do this:
1. find_prospects("{category} {city}") — up to {max_results} businesses.
2. For EACH prospect, call score_and_hook(business, business_type, city, rating, user_ratings_total, has_website, types) to get its offer + hook.
3. Collect the websites of prospects that have one and call enrich_contacts(urls=[...]) ONCE for the batch; read contacts[website] for emails/socials.
4. For each prospect with a plausible email, compose a short subject + plain-text body for its offer, opening with the hook (use the hook verbatim; never invent ratings/reviews).
5. Call export_cold_leads(campaign="{campaign}", leads=[{{email, business, business_type, city, offer, hook, subject, body}}, ...]) ONCE — it writes a CSV for manual review.
6. log_outreach_lead once per prospect (status "cold_export" if exported, else "call_queued").
Do NOT call send_email (cold goes through export_cold_leads only)."""


def main() -> None:
    p = argparse.ArgumentParser(
        description="Run one Phase-0 outreach validation batch (CSV, no send)."
    )
    p.add_argument("--city", required=True, help='City + state, e.g. "Worcester, MA"')
    p.add_argument(
        "--category", required=True, help="Trade category, e.g. plumbers, HVAC, roofers"
    )
    p.add_argument("--max", type=int, default=10, help="Max prospects (default 10)")
    p.add_argument(
        "--campaign", default="", help="Campaign label (default derived from the city)"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the task + tools only; no API calls",
    )
    args = p.parse_args()

    campaign = args.campaign or "trades-" + re.sub(
        r"[^a-z0-9]+", "-", args.city.lower()
    ).strip("-")
    task = {
        "task_id": f"PHASE0-{campaign}",
        "task_type": "outreach_compose",
        "pod": POD,
        "body": _body(args.city, args.category, args.max, campaign),
    }

    model = MODELS[ROLE]
    system_prompt = build_system_prompt(ROLE)
    tools = ROLE_TOOLS[ROLE]

    print(f"\n{'=' * 60}")
    print(f"  Phase-0 outreach  |  role={ROLE}  model={model}")
    print(
        f"  {args.category} in {args.city}  ->  campaign '{campaign}'  (max {args.max})"
    )
    print("=" * 60)

    if args.dry_run:
        print("\n--- TOOLS ---")
        print(", ".join(t["name"] for t in tools))
        print("\n--- TASK BODY ---")
        print(task["body"])
        return

    if is_pod_budget_exceeded(POD):
        print(
            f"ABORT: {POD} is over its daily spend cap (config/budgets.yaml). Try again tomorrow."
        )
        sys.exit(1)

    agent = AgentBase(ROLE, model, system_prompt, tools=tools)
    result = agent.run(task)

    print("\n--- AGENT OUTPUT ---")
    sys.stdout.buffer.write(result["output"][:3000].encode("utf-8", errors="replace"))
    print(f"\n\n--- cost ${result.get('cost_usd', 0):.4f} ---")
    print(
        "CSV (if any) -> vault/outreach/cold-export/   |   CRM -> vault/outreach/crm.md"
    )


if __name__ == "__main__":
    main()
