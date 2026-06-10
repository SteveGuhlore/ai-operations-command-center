import concurrent.futures
import logging
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.ledger.budget import is_budget_exceeded, is_pod_budget_exceeded
from runner.state.writer import update_agent_state
from runner.tasks.locker import acquire_lock, release_lock
from runner.tasks.reader import read_todo_tasks
from runner.tasks.router import route_task
from runner.tasks.transitions import move_task, write_task_output
from runner.bridge.tony_bridge import scan_and_process as scan_tony_bridge
from runner.tools.social import TOOL_SPEC_SAVE
from runner.tools.etsy import TOOL_SPEC as ETSY_TOOL_SPEC
from runner.tools.image import TOOL_SPEC as IMAGE_TOOL_SPEC
from runner.tools.audio import TOOL_SPEC as AUDIO_TOOL_SPEC
from runner.tools.web import TOOL_SPEC as WEB_TOOL_SPEC
from runner.tools.files import TOOL_SPEC as FILE_TOOL_SPEC
from runner.tools.video import TOOL_SPEC as VIDEO_TOOL_SPEC
from runner.tools.task_creator import TOOL_SPEC as TASK_CREATOR_TOOL_SPEC
from runner.tools.flag_issue import TOOL_SPEC as FLAG_ISSUE_TOOL_SPEC
from runner.tools.tony_insights import TOOL_SPEC as TONY_INSIGHTS_TOOL_SPEC
from runner.tools.tony_verdict import TOOL_SPEC as TONY_VERDICT_TOOL_SPEC
from runner.tools.tony_outcomes import TOOL_SPEC as TONY_OUTCOMES_TOOL_SPEC
from runner.tools.tony_book import TOOL_SPEC as TONY_BOOK_TOOL_SPEC
from runner.tools.stock_news import TOOL_SPEC as STOCK_NEWS_TOOL_SPEC
from runner.tools.stock_catalysts import TOOL_SPEC as CATALYSTS_TOOL_SPEC
from runner.tools.stock_data import TOOL_SPEC as STOCK_DATA_TOOL_SPEC
from runner.tools.stock_technicals import TOOL_SPEC as PRICE_HIST_TOOL_SPEC
from runner.tools.market_regime import TOOL_SPEC as REGIME_TOOL_SPEC
from runner.tools.tony_ideas import TOOL_SPEC as TONY_IDEA_TOOL_SPEC
from runner.plugins.loader import LOAD_DESIGN_SKILL_TOOL_SPEC
from runner.tools.vault_writer import write_vault_session
from runner.tools.email_sender import TOOL_SPEC as EMAIL_TOOL_SPEC
from runner.tools.places import TOOL_SPEC as PLACES_TOOL_SPEC
from runner.tools.social_dm import TOOL_SPEC as SOCIAL_DM_TOOL_SPEC
from runner.tools.vault_memory import auto_write_task_memory, WRITE_MEMORY_TOOL_SPEC as MEMORY_TOOL_SPEC
from runner.tools.inbox_reader import TOOL_SPEC as INBOX_TOOL_SPEC
from runner.tools.outreach_crm import TOOL_SPEC as OUTREACH_CRM_TOOL_SPEC
from runner.ledger.research_queue import TOOL_SPEC as RESEARCH_QUEUE_TOOL_SPEC
from runner.tools.crm_dedup import dedup_crm
from runner.tools.opportunity import TOOL_SPEC_LOG as OPP_LOG_TOOL_SPEC, TOOL_SPEC_GRADE as OPP_GRADE_TOOL_SPEC, TOOL_SPEC_UPDATE as OPP_UPDATE_TOOL_SPEC
from runner.tools.code import TOOL_SPEC as CODE_TOOL_SPEC
from runner.tools.poc_sandbox import TOOL_SPEC as POC_RUNNER_TOOL_SPEC
from runner.tools.task_creator import create_task
from runner.tools.landing import landing_exists, write_landing_state
from runner.tools.opportunity import rank_score
from runner.ledger.runway import runway_expired, pause_pod, compute_runway
from runner.scheduler.daily_jobs import (
    scout_due, mark_scout_ran,
    daily_learning_due, mark_learning_ran,
    weekly_sage_due, mark_sage_ran,
    tony_self_review_due, mark_tony_self_review_ran,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# httpx logs the full request URL at INFO, leaking ?api_key=/&token= (FRED/Finnhub/SerpAPI) into the
# launch logs. Mute it to WARNING — we don't need per-request URL noise and never want keys on disk.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

# Slash-free IDs route to Google direct (GOOGLE_AI_API_KEY, $300 free credit).
# Slash IDs route through OpenRouter (cheap third-party models).
# Anthropic / OpenAI removed — too expensive for daily autonomous runs.
MODELS: dict[str, str] = {
    "manager":                "gemini-2.5-pro",            # Atlas — best reasoning for spawning + routing
    "heavy_worker":           "moonshotai/kimi-k2.5",      # OpenRouter — cheap for long generation
    "debug_worker":           "gemini-2.5-flash",
    "content_worker":         "gemini-2.5-flash",
    "media_worker":           "moonshotai/kimi-k2.5",
    "audio_worker":           "gemini-2.5-flash",
    "guard_worker":           "gemini-2.5-flash",
    "budget_worker":          "gemini-2.5-flash",
    "digital_product_worker": "moonshotai/kimi-k2.5",
    "marketing_worker":       "gemini-2.5-flash",
    "social_media_worker":    "moonshotai/kimi-k2.5",
    "market_research_worker": "gemini-2.5-pro",            # Tony Stocks — needs sharp analysis for daily brief
    "outreach_worker":        "gemini-2.5-flash",          # Pitch — fast cheap prospect research
    "librarian":              "gemini-2.5-flash",
    "builder":                "gemini-2.5-pro",            # Clay — site generation (Pro for sharper, skill-driven design)
    "opportunity_worker":     "gemini-2.5-flash",          # Prospector — scout default; deep-dive overridden to Pro
}


def _load_task_models() -> dict[str, str]:
    """Per-task-type model overrides from config/agents.yaml `task_models:`.
    Lets every phase auto-use its most efficient model, tunable without code changes."""
    from runner.config import load_agents
    return load_agents().get("task_models", {}) or {}


# Resolved once at import; restart the runner to pick up config edits.
TASK_MODEL_OVERRIDES: dict[str, str] = _load_task_models()

MAX_CONCURRENT = 4
LOW_WATER_MARK = 2  # Atlas auto-spawns when fewer than this many tasks remain in queue (lowered for tighter outreach cadence)

# Operator pause switch for the Easy Simple Sites outreach loop (Pitch). When True,
# the cycle stops auto-reviving Pitch outreach tasks — only Tony Stocks and any
# reactive site_build (real interested leads) keep flowing. Flip to False to resume.
OUTREACH_PAUSED = True

# Tony-only focus (memory project_tony_only_focus): the Prospector/opportunity pod
# is dormant. The canonical functional pause is this flag — it gates the spawn pipeline
# AND the execute path (run_task) so the pod can neither spawn nor run. (config/agents.yaml
# `enabled` is ignored by routing; do not rely on it.) Flip to False + deploy to revive.
PROSPECTOR_PAUSED = True

# Tools each role is allowed to call
ROLE_TOOLS: dict[str, list[dict]] = {
    "social_media_worker":    [TOOL_SPEC_SAVE, IMAGE_TOOL_SPEC, AUDIO_TOOL_SPEC, VIDEO_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "media_worker":           [IMAGE_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "audio_worker":           [AUDIO_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "digital_product_worker": [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "content_worker":         [FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "debug_worker":           [WEB_TOOL_SPEC, FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "market_research_worker": [WEB_TOOL_SPEC, STOCK_DATA_TOOL_SPEC, PRICE_HIST_TOOL_SPEC, REGIME_TOOL_SPEC, STOCK_NEWS_TOOL_SPEC, CATALYSTS_TOOL_SPEC, FILE_TOOL_SPEC, TONY_INSIGHTS_TOOL_SPEC, TONY_VERDICT_TOOL_SPEC, TONY_OUTCOMES_TOOL_SPEC, TONY_BOOK_TOOL_SPEC, TONY_IDEA_TOOL_SPEC, RESEARCH_QUEUE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "outreach_worker":        [PLACES_TOOL_SPEC, WEB_TOOL_SPEC, EMAIL_TOOL_SPEC, SOCIAL_DM_TOOL_SPEC, OUTREACH_CRM_TOOL_SPEC, FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, INBOX_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "marketing_worker":       [ETSY_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "manager":                [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "heavy_worker":           [FILE_TOOL_SPEC, CODE_TOOL_SPEC, POC_RUNNER_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "opportunity_worker":     [WEB_TOOL_SPEC, FILE_TOOL_SPEC, OPP_LOG_TOOL_SPEC, OPP_GRADE_TOOL_SPEC, OPP_UPDATE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "guard_worker":           [],
    "budget_worker":          [],
    "librarian":              [FILE_TOOL_SPEC],
    "builder":                [FILE_TOOL_SPEC, IMAGE_TOOL_SPEC, MEMORY_TOOL_SPEC, LOAD_DESIGN_SKILL_TOOL_SPEC],
}


def _done_task_summary() -> str:
    done_dir = Path(__file__).parent.parent / "workspace" / "tasks" / "done"
    files = sorted(done_dir.glob("*.md"))
    if not files:
        return "No completed tasks yet."
    lines = []
    for f in files[-20:]:  # last 20 done tasks for context
        lines.append(f"- {f.stem}")
    return "\n".join(lines)


def _sync_vault() -> None:
    if sys.platform == "win32":
        return  # vault sync runs on Linux VPS only
    sync_script = Path(__file__).parent.parent / "scripts" / "vault_sync.sh"
    if not sync_script.exists():
        return
    try:
        # 30s ceiling — vault_sync.sh is a fast git push; give up rather than stall the next cycle
        subprocess.run(["bash", str(sync_script)], timeout=30, check=False)
    except Exception as exc:
        log.warning("vault sync skipped: %s", exc)


_ATLAS_SPAWN_BODY = """\
## Your Job

The task queue is low. Your number-one priority is keeping **Easy Simple Sites** (the local-outreach revenue pod) running continuously. You MUST call `create_task` at least once unless there is already a `prospect_research` task queued for outreach_worker.

## ACTIVE Revenue Streams (only spawn for these)

**Stream 1 — Easy Simple Sites (local Massachusetts web design)**
- Pitch (outreach_worker) finds no-website MA businesses, sends pitches → interested replies → Clay (builder) builds the site
- Brand: Easy Simple Sites — easysimplesites.org — signed "Stephen"
- Tiers: Starter $299, Pro $499, Premium $799
- **DEFAULT BEHAVIOR**: If no `prospect_research` task is queued for outreach_worker, spawn ONE now. Do not wait 24 hours — Pitch is allowed to run multiple times per day. The only reason to skip is "a prospect_research task is already queued".

**Stream 2 — Stock Research (Tony Stocks)**
- Tony Stocks (market_research_worker) produces a daily trading brief
- Triggered by the trading bot bridge — Atlas should NOT spawn Tony tasks unless explicitly told to

## DISABLED — Do NOT spawn tasks for these agents

The following pods are currently dormant. **NEVER call `create_task` for them**:
- Spark (social_media_worker) — video production OFF
- Muse (content_worker) — content drafting OFF
- Maker (digital_product_worker) — PDF products OFF
- Market (marketing_worker) — listing copy OFF
- Frame (media_worker) — images OFF
- Echo (audio_worker) — audio OFF

If you spawn a task for any disabled agent it will burn API money for nothing.

## What you CAN spawn

| When | Spawn |
|------|-------|
| **No outreach_worker task in the queue** | ONE `prospect_research` task for outreach_worker (this is the default — do this almost every cycle) |
| Builder has a pending intake and no current task | ONE `site_build` task for builder |

## Pitch task body template (use this exactly when spawning)

```
title: "Pitch: Daily Outreach"
task_type: prospect_research
assigned_agent: outreach_worker
pod: local_outreach_pod
priority: high
body: |
  Run the standard outreach workflow for Easy Simple Sites (easysimplesites.org).

  GEO ROTATION — work through these in order, picking cities not used in the last 3 runs.
  Check your memory for recently covered cities and skip them.

  MASSACHUSETTS (primary — exhaust these first):
  Boston, Worcester, Springfield, Cambridge, Lowell, Brockton, Quincy, Lynn,
  New Bedford, Fall River, Newton, Somerville, Framingham, Haverhill, Waltham,
  Salem, Medford, Everett, Lawrence, Malden, Revere, Weymouth, Peabody, Taunton,
  Attleboro, Fitchburg, Leominster, Chicopee, Holyoke, Pittsfield, Westfield,
  Agawam, Northampton, Amherst, Gloucester, Plymouth, Barnstable, Methuen,
  Chelsea, Amesbury, Andover, Beverly, Billerica, Burlington, Chelmsford,
  Dracut, Marlborough, Milford, Natick, Norwood, Randolph, Stoughton, Tewksbury,
  Watertown, Woburn, Dedham, Lexington, Needham, Milton, Canton, Mansfield

  STALENESS RULE — if you find fewer than 5 new unique prospects across 2+ MA city
  searches in this run, MA inventory is getting thin. Add one city from a neighboring
  state to your search for this run and note it in memory.

  NEIGHBORING STATES (use when MA is getting stale):
  Rhode Island: Providence, Cranston, Warwick, Pawtucket, Woonsocket, East Providence
  Connecticut: Hartford, New Haven, Bridgeport, Stamford, Waterbury, New Britain, Norwich
  New Hampshire: Manchester, Nashua, Concord, Dover, Portsmouth, Rochester
  Maine: Portland, Lewiston, Bangor, Auburn, Augusta
  Vermont: Burlington, Rutland, South Burlington, Barre

  CATEGORIES — rotate broadly, pick ones not used in the last 2 runs:
  hair salons, barbershops, nail salons, beauty salons, eyelash studios, spas,
  auto repair shops, car washes, auto detailing,
  restaurants, food trucks, bakeries, cafes, catering services,
  plumbers, electricians, HVAC contractors, roofers, painters, handymen, general contractors,
  cleaning services, carpet cleaners, pest control,
  landscaping services, lawn care, tree services,
  dog groomers, pet shops, boarding kennels,
  daycares, after-school programs, tutoring centers,
  martial arts studios, yoga studios, fitness studios, personal trainers,
  tattoo shops, massage therapists,
  florists, photographers, videographers,
  dry cleaners, laundromats, tailors,
  moving companies, junk removal,
  accountants, notaries, insurance agents

  CONTACT LOOKUP — after find_prospects, for each no-website business call web_research
  (action=search, query="[Business Name] [City] MA contact email OR instagram") ONCE per
  prospect. If email found → send_email + status email_sent. If IG handle found →
  send_instagram_dm + status dm_queued. If nothing found → status call_queued (phone only).
  Limit to 1 web_research call per prospect — do not retry.

  Sign all pitches as Stephen, easysimplesites.org. Never reference any other brand.
```

## Already Done (don't duplicate)

{done_summary}

## Instructions

The only acceptable reason to call `create_task` zero times is: a `prospect_research` task for outreach_worker is ALREADY in the queue. Otherwise, you MUST spawn one using the template above. Idle queues kill the revenue pipeline.
"""


def _pitch_is_alive() -> bool:
    """Return True if outreach_worker has a task in todo or in_progress."""
    tasks_root = Path(__file__).parent.parent / "workspace" / "tasks"
    for folder in ("todo", "in_progress"):
        d = tasks_root / folder
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                if "assigned_agent: outreach_worker" in content:
                    return True
            except OSError:
                pass
    return False


_PITCH_TASK_BODY = """\
Easy Simple Sites outreach. Find Massachusetts local businesses with NO website.

- Search 3 cities, 1 category each. Pick cities/categories not used recently (check memory).
- For each no-website business: call web_research once (query: "[Name] [City] MA contact email OR instagram") to find email/IG handle.
- If email found → send_email immediately, status: email_sent. If IG found → send_instagram_dm, status: dm_queued. If nothing → status: call_queued.
- Append new rows to vault/outreach/crm.md using file_editor action=append. NEVER use action=write.
- Row format: | Business | Type | City, MA | contact | channel | status | YYYY-MM-DD | notes |
- End: call create_task to queue next run, call write_memory to log cities/categories tried.

Sign as Stephen, easysimplesites.org.
"""


def _maybe_spawn_planning_task() -> None:
    # Pitch is self-perpetuating (Step 10 of outreach_worker creates its own next task).
    # Only intervene if the loop has died — create a Pitch task directly, no Atlas needed.
    if not OUTREACH_PAUSED and not _pitch_is_alive():
        from runner.tools.task_creator import create_task
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        result = create_task(
            title="Pitch: Continuous Outreach",
            body=_PITCH_TASK_BODY,
            assigned_agent="outreach_worker",
            task_type="prospect_research",
            pod="local_outreach_pod",
            priority="high",
        )
        log.info("Pitch loop was dead — revived directly: %s", result.get("task_id", result))
        return

    # Atlas planning: only fire when a genuine strategic decision is needed.
    # (New pods, builder intake, etc.) — NOT for routine Pitch re-queueing.
    remaining = read_todo_tasks()
    has_planning = any(t.get("task_type") == "planning" for t in remaining)
    strategic_needed = any(
        t.get("task_type") in ("site_build",) for t in remaining
    )
    if strategic_needed and not has_planning:
        from runner.tools.task_creator import create_task
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        body = _ATLAS_SPAWN_BODY.format(done_summary=_done_task_summary())
        result = create_task(
            title="Atlas: Spawn Next Revenue Tasks",
            body=body,
            assigned_agent="manager",
            task_type="planning",
            pod="management",
            priority="high",
            task_id=f"ATLAS-PLAN-{ts}",
        )
        log.info("Strategic task needed — spawned Atlas: %s", result.get("task_id"))


def _doomsday_banner() -> str:
    """Live runway state as an urgent header — makes the doomsday clock LITERAL and
    concrete (real days/dollars) at the top of every Prospector task, so he races it."""
    r = compute_runway()
    return (
        "TICKING TIME BOMB — your survival runway, read it as a literal countdown:\n"
        f"  - {r['days_remaining']} day(s) of runway left (the pod is PAUSED and you STOP "
        f"running at zero; survive-by {r['survive_by']}).\n"
        f"  - ${r['spend']:.2f} burned of ${r['effective_allowance_usd']:.2f} allowance.\n"
        f"  - REAL revenue booked so far: ${r['real_revenue']:.2f}. The clock is extended "
        "ONLY by real paying customers — never by scores or a pile of ideas.\n"
        "  - So every cycle counts. Surface the BEST, most novel, monetizable-THIS-WEEK "
        "ideas, relentlessly. Quality and speed to first dollar are survival.\n\n"
    )


_SCOUT_TASK_BODY = """\
Run the Prospector opportunity scout for opportunity_pod. You never stop hunting — if the
backlog ever empties, you scout again. Constant flow of the BEST ideas is the job.

1. Read vault/opportunities/ledger.md first — skip slugs already present, never re-scout them.
2. Web-research the FRESHEST, highest-signal AI-agent business ideas, niches, and unmet pain
   points. Produce 15-20 genuinely NEW candidates — novel angles, not me-too wrappers, not
   re-skins of ideas already in the ledger.
3. Score each new idea (six dimensions 0-10) and call log_opportunity. Be honest, but do NOT
   reflexively dock big/proven markets — name the defensible wedge or don't reject it.
4. For each idea with composite >= 75, create an opportunity_deepdive task (opportunity_worker,
   opportunity_pod). Prioritize the ones with the fastest concrete path to a paying customer.
5. write_memory(entry_type=metric) with counts scouted / >=75.
"""


def _poc_built(slug: str) -> bool:
    """True if a PoC has already been scaffolded for this slug under
    workspace/poc/<slug>/ — the signal that the build step is done and the grade
    step should run next."""
    from runner.tools.poc_sandbox import POC_ROOT
    return (POC_ROOT / slug).is_dir()


def _opportunity_task_pending() -> bool:
    """True if any Prospector pipeline task is already queued, so the cycle should
    let it run rather than spawn another."""
    from runner.tools.task_creator import _has_pending_task
    for agent, tt in (("opportunity_worker", "opportunity_scout"),
                      ("opportunity_worker", "opportunity_deepdive"),
                      ("heavy_worker", "poc_build"),
                      ("opportunity_worker", "poc_grade")):
        if _has_pending_task(agent, tt):
            return True
    return False


def _advance_opportunity_pipeline() -> None:
    """Keep Prospector perpetually working. Each cycle, if no opportunity task is
    already queued, spawn the next pipeline step so he flows scout -> deep-dive
    (every idea, not just >=75) -> PoC build -> graduate (landing build) -> fresh
    scout, never idling. The opportunity_pod daily cap is the only guardrail."""
    if PROSPECTOR_PAUSED:
        log.info("Pipeline: Prospector paused by PROSPECTOR_PAUSED flag — skipping.")
        return
    from runner.tools.opportunity import read_ledger

    if is_pod_budget_exceeded("opportunity_pod"):
        log.info("Pipeline: opportunity_pod budget reached — pausing Prospector.")
        return

    # Doomsday clock: the pod survives only while its runway holds. The runway
    # burns with spend/time and is extended only by REAL logged revenue, so an
    # expired runway means "earned nothing real in time" — pull the plug
    # (reversible auto-pause; operator revives via dashboard/CLI).
    if runway_expired():
        pause_pod()
        log.warning("Pipeline: Prospector runway EXPIRED — pod auto-paused (no real revenue in time).")
        return

    # If any opportunity work is already queued, let the 10-min cycle run it.
    if _opportunity_task_pending():
        return

    rows = read_ledger()

    # 0) SHIP FIRST: graduate a promising PoC into a draft landing page. This is
    # the closest step to real revenue, so it outranks speculative research —
    # otherwise the constant backlog of scouted/deepdived ideas starves graduated
    # winners and nothing ever ships (the stall that stranded ai-b2b-intent-data-analyzer).
    promising = [r for r in rows
                 if r.get("poc") == "promising" and not landing_exists(r["slug"])]
    if promising:
        top = max(promising, key=rank_score)
        write_landing_state(top["slug"], status="queued")
        create_task(
            title=f"Landing build: {top['slug']}",
            body=(f"Build a one-page product landing page for the graduated opportunity "
                  f"[[{top['slug']}]]. Read its value prop, who-pays, and pricing from "
                  f"vault/opportunities/{top['slug']}.md. Follow the 'Product Landing Page "
                  f"(landing_build)' section of your system prompt. Save the page to "
                  f"workspace/sites/{top['slug']}/index.html with the CTA button's href set to "
                  f"the literal placeholder __STRIPE_PAYMENT_LINK__ (do NOT invent a URL — the "
                  f"operator injects the live Stripe Payment Link at deploy). End your summary "
                  f"with: LANDING DRAFTED: {top['slug']}"),
            assigned_agent="builder", task_type="landing_build",
            pod="opportunity_pod", priority="normal")
        log.info("Pipeline: landing build %s", top["slug"])
        return

    # 1) Deep-dive the highest-scored idea not yet researched.
    scouted = [r for r in rows if r.get("phase") == "scouted"]
    if scouted:
        top = max(scouted, key=rank_score)
        create_task(
            title=f"Deep-dive: {top['slug']}",
            body=(f"Deep-dive the opportunity [[{top['slug']}]]. Research market size, "
                  f"competitors, who pays, and pricing. Re-score with evidence, then call "
                  f"update_opportunity(slug, composite=<new>, phase='deepdived') and append "
                  f"a Build Spec to vault/opportunities/{top['slug']}.md."),
            assigned_agent="opportunity_worker", task_type="opportunity_deepdive",
            pod="opportunity_pod", priority="normal")
        log.info("Pipeline: deep-dive %s", top["slug"])
        return

    # 2) Build a PoC for the best researched idea that doesn't have one yet.
    buildable = [r for r in rows if r.get("phase") == "deepdived"
                 and r.get("poc", "—") in ("—", "-", "") and r["composite"] >= 70
                 and not _poc_built(r["slug"])]
    if buildable:
        top = max(buildable, key=rank_score)
        create_task(
            title=f"PoC build: {top['slug']}",
            body=(f"Build a minimal sandboxed proof-of-concept for [[{top['slug']}]] following "
                  f"its Build Spec in vault/opportunities/{top['slug']}.md. Produce a runnable "
                  f"artifact under workspace/poc/{top['slug']}/ that demonstrates the core value."),
            assigned_agent="heavy_worker", task_type="poc_build",
            pod="opportunity_pod", priority="normal")
        log.info("Pipeline: PoC build %s", top["slug"])
        return

    # 2.4) Grade a PoC that has been built but not yet graded. The pipeline owns
    # poc_grade-task creation (correct task_type) so it no longer depends on the
    # builder remembering to spawn it — the historical source of mislabeled,
    # never-graded tasks that left PoCs stuck at poc="—".
    gradeable = [r for r in rows
                 if r.get("poc", "—") in ("—", "-", "") and _poc_built(r["slug"])]
    if gradeable:
        top = max(gradeable, key=rank_score)
        create_task(
            title=f"PoC grade: {top['slug']}",
            body=(f"Grade the proof-of-concept for [[{top['slug']}]] under "
                  f"workspace/poc/{top['slug']}/. Review output.txt and the demo files against "
                  f"the Build Spec in vault/opportunities/{top['slug']}.md. You MUST finish by "
                  f"calling grade_poc(slug='{top['slug']}', verdict=..., reason=...) with verdict "
                  f"promising/weak/dead — the task is NOT complete until grade_poc returns success. "
                  f"Do not mark this task done without calling grade_poc."),
            assigned_agent="opportunity_worker", task_type="poc_grade",
            pod="opportunity_pod", priority="normal")
        log.info("Pipeline: PoC grade %s", top["slug"])
        return

    # 3) Everything processed — scout a fresh batch of ideas.
    result = create_task(
        title="Prospector: Opportunity Scout", body=_doomsday_banner() + _SCOUT_TASK_BODY,
        assigned_agent="opportunity_worker", task_type="opportunity_scout",
        pod="opportunity_pod", priority="low")
    if result.get("success") or result.get("skipped"):
        mark_scout_ran()
    log.info("Pipeline: fresh scout batch — %s", result.get("task_id", result))


def _maybe_run_learning() -> None:
    if not daily_learning_due(hour_after=2):
        return
    root = Path(__file__).parent.parent
    log.info("Daily learning hook firing — improvement_loop + opportunity_synthesis + design_synthesis + outreach_synthesis")
    subprocess.run([sys.executable, str(root / "scripts" / "improvement_loop.py")], cwd=root, check=False)
    for script in ("opportunity_synthesis.py", "design_synthesis.py", "outreach_synthesis.py"):
        syn = root / "scripts" / script
        if syn.exists():
            subprocess.run([sys.executable, str(syn)], cwd=root, check=False)
    if weekly_sage_due():
        from runner.tools.task_creator import create_task
        create_task(
            title="Sage: Weekly Memory Synthesis",
            body="Run the full librarian synthesis workflow across all agent memory logs.",
            assigned_agent="librarian", task_type="memory_synthesis",
            pod="management", priority="low",
        )
        mark_sage_ran()
    mark_learning_ran()


def run_task(task: dict) -> dict:
    task_id = task["task_id"]
    role_id = route_task(task)

    if not acquire_lock(task_id, role_id):
        log.info("Task %s already locked — skipping", task_id)
        return {"skipped": True, "task_id": task_id}

    # Same lane as the cycle gate: off-hours uses its own cap, so a task that passed the
    # cycle's off-hours check isn't then bounced here by the depleted daytime cap.
    if is_budget_exceeded(off_hours=_is_market_closed()):
        release_lock(task_id)
        log.warning("Budget cap reached — skipping %s", task_id)
        return {"skipped": True, "task_id": task_id}

    pod = task.get("pod")
    # Prospector is dormant: clear any straggler opportunity_pod task ONCE (fail it)
    # instead of letting the pod-cap skip path leave it in todo to retry every cycle.
    # Must run BEFORE the budget check below. move_task has no reason field, so record
    # the reason explicitly via the task output.
    if PROSPECTOR_PAUSED and pod == "opportunity_pod":
        log.info("run_task: opportunity_pod task %s cleared — PROSPECTOR_PAUSED", task_id)
        move_task(task_id, "todo", "failed")
        write_task_output(task_id, "Cleared: Prospector is paused (PROSPECTOR_PAUSED).", "failed")
        release_lock(task_id)
        return {"skipped": True, "task_id": task_id, "reason": "prospector paused"}

    if pod and is_pod_budget_exceeded(pod):
        release_lock(task_id)
        log.warning("Pod budget cap reached for %s — skipping %s", pod, task_id)
        return {"skipped": True, "task_id": task_id, "reason": f"{pod} daily cap reached"}

    try:
        update_agent_state(role_id, "working", task_id)
        move_task(task_id, "todo", "in_progress")

        model = TASK_MODEL_OVERRIDES.get(task.get("task_type")) or MODELS.get(role_id, "gemini-2.5-flash-lite")
        tools = ROLE_TOOLS.get(role_id, [])
        agent = AgentBase(role_id, model, build_system_prompt(role_id), tools=tools)
        result = agent.run(task)

        write_task_output(task_id, result["output"], "in_progress")
        write_vault_session(task_id, role_id, result)
        auto_write_task_memory(role_id, task_id, task.get("task_type", "unknown"), "success", result.get("output", ""))
        if role_id == "outreach_worker":
            removed = dedup_crm()
            if removed:
                log.info("CRM dedup removed %d duplicate row(s)", removed)
        move_task(task_id, "in_progress", "done")
        update_agent_state(role_id, "idle", "", f"completed {task_id}")
        log.info("%s completed %s ($%.4f)", role_id, task_id, result["cost_usd"])
        return result

    except Exception as exc:
        log.error("%s failed %s: %s", role_id, task_id, exc)
        write_vault_session(task_id, role_id, {"error": str(exc)})
        auto_write_task_memory(role_id, task_id, task.get("task_type", "unknown"), "failure", str(exc))
        try:
            move_task(task_id, "in_progress", "failed")
        except Exception:
            pass
        update_agent_state(role_id, "error", task_id, str(exc))
        return {"error": str(exc), "task_id": task_id}

    finally:
        release_lock(task_id)


_STALE_TASK_AGE_S = 780  # 13 min — just past the 12-min per-task hard cap
_MAX_TASK_RESUMES = 3


def _reap_stale_tasks(ws: Path | None = None) -> None:
    """Self-heal: re-queue any in_progress task older than the per-task hard cap so a task
    never stays stuck (crash, killed/overlapping cycle). Age-gated so it never touches a task
    still legitimately running this cycle. A bounded resume_count sends a poison task to
    failed/ instead of looping forever."""
    if ws is None:
        ws = Path(__file__).parent.parent / "workspace"
    ip, todo, failed, locks = (ws / "tasks" / "in_progress", ws / "tasks" / "todo",
                               ws / "tasks" / "failed", ws / "locks")
    if not ip.exists():
        return
    now = time.time()
    todo.mkdir(parents=True, exist_ok=True)
    failed.mkdir(parents=True, exist_ok=True)
    for f in ip.glob("*.md"):
        try:
            if now - f.stat().st_mtime < _STALE_TASK_AGE_S:
                continue
            # Age alone can't prove death: a worker thread that outlived its cycle's future
            # timeout is still executing. If the lock's owner pid is alive, leave it be —
            # reaping here would re-queue the task and run it twice concurrently. But a live
            # pid can also be a long-lived process (dashboard) whose thread died, so past 4x
            # the stale age reap regardless rather than wedge the task forever.
            from runner.tasks.locker import lock_owner_alive
            if (now - f.stat().st_mtime < _STALE_TASK_AGE_S * 4) and lock_owner_alive(f.stem):
                continue
            text = f.read_text(encoding="utf-8")
            m = re.search(r"^resume_count:\s*(\d+)", text, re.MULTILINE)
            count = int(m.group(1)) if m else 0
            for lk in locks.glob(f"*{f.stem}*.lock"):
                lk.unlink(missing_ok=True)
            if count >= _MAX_TASK_RESUMES:
                f.rename(failed / f.name)
                log.warning("Reaped poison task -> failed/ (%d resumes): %s", count, f.name)
                continue
            if m:
                text = re.sub(r"^resume_count:\s*\d+", f"resume_count: {count + 1}", text, count=1, flags=re.MULTILINE)
            else:
                text = re.sub(r"^(status:.*)$", r"\1\nresume_count: 1", text, count=1, flags=re.MULTILINE)
            text = re.sub(r"^status:\s*\w+", "status: todo", text, count=1, flags=re.MULTILINE)
            (todo / f.name).write_text(text, encoding="utf-8")
            f.unlink()
            log.warning("Reaped stale in_progress task -> todo: %s", f.name)
        except OSError:
            continue


def _maybe_refresh_regime() -> None:
    """Refresh the macro-regime cache in a fire-and-forget daemon thread when it's stale, so the
    networked yfinance/FRED fetch can NEVER stall the cycle. Briefs read the cache, not the fetch."""
    try:
        from runner.tools.market_regime import cache_stale, refresh_regime_cache
        if not cache_stale(30.0):
            return
    except Exception as exc:
        log.info("regime refresh skip: %s", exc)
        return

    def _run():
        try:
            refresh_regime_cache(30.0)
        except Exception as exc:
            log.info("regime refresh failed: %s", exc)

    threading.Thread(target=_run, daemon=True, name="regime-refresh").start()


def _maybe_run_tony_self_review() -> None:
    """Weekly: once enough verdicts are graded against bot outcomes, spawn a self-review
    task so Tony learns from his own hit-rate. Silent no-op until outcomes exist."""
    if not tony_self_review_due():
        return
    from runner.ledger.tony_scorecard import compute_record
    rec = compute_record()
    if rec.get("status") != "scored" or rec.get("graded", 0) < 3:
        return
    create_task(
        title="Tony: Weekly Self-Review",
        body=("Grade your own record. Read tony_stocks_record.json (your win rate, agreement "
              "matrix vs the scanner, confidence calibration) and your last 2 weeks of verdicts "
              "vs outcomes. Where were you right/wrong and WHY? Update "
              "vault/tony-stocks/pattern-library.md with concrete, evidence-tagged lessons "
              "(setups/fundamentals you win or lose on). Finish with one write_tony_insight "
              "naming your single biggest adjustment for next week."),
        assigned_agent="market_research_worker", task_type="tony_self_review",
        pod="stock_research_pod", priority="normal")
    mark_tony_self_review_ran()
    log.info("Spawned Tony weekly self-review (graded=%d)", rec.get("graded", 0))


def _build_recap_lines(acct: dict, rec: dict, realized: dict) -> list:
    """Pure (testable) recap body per spec §3.D: equity + day Δ, open positions + unrealized P/L,
    closed-today realized P/L, and the RELABELED scanner-verdict accuracy line."""
    equity = acct.get("equity")
    last_equity = acct.get("last_equity")
    pos = acct.get("open_positions", []) or []
    if isinstance(equity, (int, float)):
        line_eq = f"Equity: ${equity:,.0f}"
        if isinstance(last_equity, (int, float)) and last_equity:
            delta = equity - last_equity
            pct = delta / last_equity * 100
            arrow = "▲" if delta >= 0 else "▼"
            line_eq += f"  ({arrow} ${delta:,.0f} / {pct:+.2f}% on the day)"
    else:
        line_eq = "Equity: n/a"

    unreal = sum(float(p.get("unrealized_pl", 0) or 0) for p in pos)
    line_open = f"Open: {len(pos)} positions · unrealized P/L ${unreal:,.2f}"

    t = realized.get("today", {})
    line_closed = (f"Closed today: {t.get('count', 0)}  "
                   f"({t.get('wins', 0)} win / {t.get('losses', 0)} loss) "
                   f"· realized P/L ${float(t.get('realized_pl', 0) or 0):,.2f}")

    wr = rec.get("win_rate")
    line_acc = (f"Scanner-verdict accuracy: {wr}% ({rec.get('graded', 0)})"
                if wr is not None else "Scanner-verdict accuracy: n/a yet")
    return [line_eq, line_open, line_closed, line_acc]


def _maybe_send_daily_summary() -> None:
    """Once a day, push a Telegram digest of Tony's book + record to the operator. Cosmetic,
    fail-soft, no-op when TONY_NOTIFY is off."""
    try:
        import json
        from datetime import date as _date
        from pathlib import Path as _Path
        from runner.tools.notify import notify_daily, _channel
        if _channel() in ("", "off"):
            return
        state = _Path(__file__).parent.parent / "workspace" / "notify-daily-state.json"
        today = str(_date.today())
        try:
            if json.loads(state.read_text()).get("date") == today:
                return
        except Exception:
            pass
        from runner.ledger.alpaca_paper import account_record
        from runner.ledger.tony_scorecard import compute_record
        from runner.ledger.tony_realized import summary as realized_summary
        acct = account_record()
        if acct.get("status") != "ok":
            return
        rec = compute_record()
        realized = realized_summary()
        from runner.tools.tony_voice import say_daily_header
        equity, last_eq = acct.get("equity"), acct.get("last_equity")
        day_delta = (float(equity) - float(last_eq)) if isinstance(equity, (int, float)) \
            and isinstance(last_eq, (int, float)) else None
        header = say_daily_header(equity, day_delta)
        notify_daily("\n".join([header] + _build_recap_lines(acct, rec, realized)))
        try:  # Phase 3: a first-person narrative wrap alongside the metric digest (opt-in, fail-soft)
            from runner.tools.tony_synthesis import synth_enabled, send_daily_wrap
            if synth_enabled():
                send_daily_wrap()
        except Exception as exc:
            log.info("daily wrap failed: %s", exc)
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"date": today}))
    except Exception as exc:
        log.info("daily summary failed: %s", exc)


def _maybe_send_weekly_synthesis() -> None:
    """Phase 3: once per ISO week, push Tony's first-person week-in-review + 'what I'm learning'
    narratives. Opt-in (TONY_SYNTH=on), fail-soft, no-op when notify/synth is off."""
    try:
        import json
        from datetime import date as _date
        from pathlib import Path as _Path
        from runner.tools.notify import _channel
        from runner.tools.tony_synthesis import synth_enabled, send_weekly_review, send_learning_digest
        if _channel() in ("", "off") or not synth_enabled():
            return
        state = _Path(__file__).parent.parent / "workspace" / "notify-weekly-state.json"
        week = "-".join(str(x) for x in _date.today().isocalendar()[:2])  # e.g. "2026-23"
        try:
            if json.loads(state.read_text()).get("week") == week:
                return
        except Exception:
            pass
        send_weekly_review()
        send_learning_digest()
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"week": week}))
    except Exception as exc:
        log.info("weekly synthesis failed: %s", exc)


def _is_market_closed() -> bool:
    try:
        from runner.ledger.market_clock import market_session
        return market_session() == "closed"
    except Exception as exc:
        log.info("market session check failed: %s", exc)
        return False


def _maybe_stage_research_wave() -> None:
    """Component B: when the market is closed, stage one off-market research wave for the next open.
    Cosmetic / fail-soft — never breaks the cycle."""
    try:
        from runner.bridge.research_wave import maybe_stage_research_wave
        res = maybe_stage_research_wave()
        if res.get("staged"):
            log.info("Off-market research wave staged: %d tasks for the %s open",
                     res.get("task_count", 0), res.get("open_date"))
    except Exception as exc:
        log.warning("research wave staging failed: %s", exc)


def _maybe_stage_research_followups() -> None:
    """After the main wave drains, stage the next deeper research round (self-learning → deepen →
    broaden), one round per drain, then idle. Fills idle closed-hours with genuine NEW research.
    Cosmetic / fail-soft — never breaks the cycle."""
    try:
        from runner.bridge.research_wave import maybe_stage_research_followups
        res = maybe_stage_research_followups()
        if res.get("staged"):
            log.info("Off-market follow-up round %d staged: %d tasks for the %s open",
                     res.get("round"), res.get("task_count", 0), res.get("open_date"))
    except Exception as exc:
        log.warning("research follow-up staging failed: %s", exc)


def _maybe_handle_telegram_chat() -> None:
    """Ensure the background Telegram long-poll thread is running (idempotent, fail-soft).
    Real-time replies happen on that thread (near-instant), not in the 180s cycle."""
    try:
        from runner.tools.telegram_inbox import start_poller
        start_poller()
    except Exception as exc:
        log.info("telegram poller start failed: %s", exc)


def _maybe_preopen_backstop() -> None:
    """The 09:25 ET cron is primary; this is the redundant backstop + missing-flush alert (the
    09:25 job was lost once in the Windows->Linux move). In the pre-open window (market closed,
    just before the open) run the reset if the cron hasn't yet; once the market is open with no
    flush today, alert instead (do NOT flush mid-session). Fail-soft — never breaks the cycle."""
    try:
        from runner.scheduler.daily_jobs import preopen_done_today, alert_due, mark_alert_ran
        if preopen_done_today():
            return
        from datetime import datetime, time as _t
        from runner.ledger.market_clock import _ET, _HOLIDAYS_2026, market_session
        now = datetime.now(_ET)
        if now.weekday() >= 5 or now.strftime("%Y-%m-%d") in _HOLIDAYS_2026:
            return
        session = market_session()
        t = now.timetz().replace(tzinfo=None)
        if session == "closed" and _t(9, 5) <= t < _t(9, 30):
            from runner.ledger.preopen import run_preopen_reset
            run_preopen_reset()
            log.info("pre-open backstop: ran the reset from the runner (cron had not yet)")
            try:
                from runner.tools.notify import notify
                notify("🔄 Pre-open reset ran from the runner backstop (the 09:25 cron hadn't run yet).")
            except Exception:
                pass
        elif session == "open" and alert_due("preopen_missing"):
            try:
                from runner.tools.notify import notify
                notify("⚠️ Pre-open flush did NOT run today — verdicts were not cleared before the "
                       "open. Check the 09:25 cron (scripts/preopen_reset.py).")
            except Exception:
                pass
            mark_alert_ran("preopen_missing")
    except Exception as exc:
        log.info("preopen backstop skipped: %s", exc)


def _maybe_health_alert() -> None:
    """Once an hour, warn the operator (Telegram) about a verdict backlog or an oversized position
    — the failure modes behind the June 2026 pyramiding. Read-only + fail-soft."""
    try:
        from runner.scheduler.daily_jobs import health_alert_due, mark_health_check_ran
        if not health_alert_due(interval_hours=1):
            return
        from runner.tools.health_monitor import collect_issues
        issues = collect_issues()
        if issues:
            try:
                from runner.tools.notify import notify
                notify("⚠️ Tony health check:\n- " + "\n- ".join(issues))
            except Exception:
                pass
        mark_health_check_ran()
    except Exception as exc:
        log.info("health alert skipped: %s", exc)


def _maybe_intraday_sweep() -> None:
    """Continuous intraday research — flag-gated, DEFAULT OFF. When the market is OPEN, top up
    deep-dives for cooled-down names across BOTH sources — the bot's scanned universe (all tiers in
    the latest bridge) AND Tony's own originated ideas — instead of only firing on the bot's next
    bridge. The per-symbol cooldown paces it (a name re-grades at most every few hours) and the
    stock_research_pod budget cap is the hard $ ceiling. Set TONY_INTRADAY_SWEEP=on to enable.
    Fail-soft — never breaks the cycle."""
    import os
    if os.environ.get("TONY_INTRADAY_SWEEP", "off").strip().lower() != "on":
        return
    try:
        if _is_market_closed():
            return  # off-market is the research wave's job
        from runner.bridge.tony_bridge import _latest_bridge_md, _fanout_deepdives
        slug, md = _latest_bridge_md()
        if md:
            _fanout_deepdives(slug, md)
    except Exception as exc:
        log.info("intraday sweep skipped: %s", exc)


def run_cycle() -> None:
    _maybe_handle_telegram_chat()  # Phase 2 inbound chat — free + read-only, runs even if budget-capped
    _maybe_preopen_backstop()  # cron-independent pre-open reset + missing-flush alert (before budget gate)
    _maybe_health_alert()      # hourly backlog / oversized-position warning    # Off-hours research runs in its own high/uncapped budget lane so a depleted daytime budget
    # never aborts the overnight wave; the daytime cap is unchanged when the market is open.
    off_hours = _is_market_closed()
    if is_budget_exceeded(off_hours=off_hours):
        log.warning("Budget cap reached (%s lane) — skipping cycle.",
                    "off-hours" if off_hours else "daytime")
        return

    _reap_stale_tasks()
    _maybe_refresh_regime()   # off-path: keeps the macro cache warm for the briefs below
    scan_tony_bridge()
    _maybe_intraday_sweep()  # flag-gated continuous intraday deep-dives (scanner + Tony's ideas)
    try:
        from runner.ledger.equity_history import snapshot as _equity_snapshot
        _equity_snapshot()  # one Tony-vs-bot equity point each cycle for the head-to-head curve
    except Exception as exc:
        log.warning("equity snapshot failed: %s", exc)
    tasks = read_todo_tasks()
    if not tasks:
        log.info("No tasks in queue.")
        _maybe_spawn_planning_task()
        _advance_opportunity_pipeline()
        _maybe_run_learning()          # idle-time learning must still fire (queue is empty overnight)
        _maybe_run_tony_self_review()
        _maybe_stage_research_wave()   # Component B: off-market research wave for the next open
        _maybe_stage_research_followups()  # deeper self-learning rounds once the wave drains
        # Keep the paper book healthy between bridges: re-attach protection to any naked
        # position, detect/notify exits (stop/target fills), and refresh the record — these
        # must NOT wait for the next bridge or stop-outs go unprotected and unannounced.
        try:
            from runner.ledger.alpaca_paper import sync as alpaca_sync
            alpaca_sync()
        except Exception as exc:
            log.warning("idle alpaca sync failed: %s", exc)
        try:
            from runner.ledger.alpaca_paper import reconcile_realized
            reconcile_realized()  # keep the realized ledger true to Alpaca, overnight too
        except Exception as exc:
            log.warning("idle realized reconcile failed: %s", exc)
        try:
            from runner.ledger.tony_scorecard import write_record
            write_record()
        except Exception as exc:
            log.warning("idle scorecard refresh failed: %s", exc)
        return

    batch = tasks[:MAX_CONCURRENT]
    log.info("Dispatching %d task(s)", len(batch))

    TASK_TIMEOUT = 720  # 12 minutes hard cap per task
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures_map = {executor.submit(run_task, t): t for t in batch}
        for future in concurrent.futures.as_completed(futures_map):
            task = futures_map[future]
            task_id = task.get("task_id", "unknown")
            try:
                future.result(timeout=TASK_TIMEOUT)
            except concurrent.futures.TimeoutError:
                log.error("Task %s exceeded %ds timeout — cleaning up", task_id, TASK_TIMEOUT)
                try:
                    move_task(task_id, "in_progress", "failed")
                except Exception:
                    pass
                try:
                    release_lock(task_id)
                except Exception:
                    pass
            except Exception as exc:
                log.error("Unhandled task error: %s", exc)

    _maybe_spawn_planning_task()
    _advance_opportunity_pipeline()
    _maybe_run_learning()
    _maybe_run_tony_self_review()
    _maybe_send_daily_summary()
    _maybe_send_weekly_synthesis()   # Phase 3: weekly first-person review + learning digest
    try:
        from runner.tools import tony_nudges
        tony_nudges.maybe_equity_high()
        if _is_market_closed():
            from datetime import date
            tony_nudges.maybe_eod_signoff(str(date.today()))
    except Exception as exc:
        log.info("nudges failed: %s", exc)
    try:
        from runner.ledger.alpaca_paper import reconcile_realized
        reconcile_realized()  # rebuild realized ledger from Alpaca fills (captures all real exits)
    except Exception as exc:
        log.warning("realized reconcile failed: %s", exc)
    try:
        from runner.ledger.tony_scorecard import write_record
        write_record()  # refresh tony_stocks_record.json for the Cockpit (cheap, degrades safely)
    except Exception as exc:
        log.warning("scorecard refresh failed: %s", exc)
    try:
        from runner.ledger.alpaca_paper import sync as alpaca_sync
        res = alpaca_sync()  # execute fresh verdicts into Tony's paper book (no-op without keys)
        if res.get("executed"):
            log.info("Alpaca paper: executed %d order(s)", res["executed"])
    except Exception as exc:
        log.warning("alpaca paper sync failed: %s", exc)
    _sync_vault()


if __name__ == "__main__":
    run_cycle()
