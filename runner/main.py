import concurrent.futures
import logging
import subprocess
import sys
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
from runner.tools.vault_writer import write_vault_session
from runner.tools.email_sender import TOOL_SPEC as EMAIL_TOOL_SPEC
from runner.tools.places import TOOL_SPEC as PLACES_TOOL_SPEC
from runner.tools.social_dm import TOOL_SPEC as SOCIAL_DM_TOOL_SPEC
from runner.tools.vault_memory import auto_write_task_memory, WRITE_MEMORY_TOOL_SPEC as MEMORY_TOOL_SPEC
from runner.tools.inbox_reader import TOOL_SPEC as INBOX_TOOL_SPEC
from runner.tools.crm_dedup import dedup_crm
from runner.tools.opportunity import TOOL_SPEC_LOG as OPP_LOG_TOOL_SPEC
from runner.tools.code import TOOL_SPEC as CODE_TOOL_SPEC

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
    "builder":                "gemini-2.5-flash",          # Clay — site generation
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

# Tools each role is allowed to call
ROLE_TOOLS: dict[str, list[dict]] = {
    "social_media_worker":    [TOOL_SPEC_SAVE, IMAGE_TOOL_SPEC, AUDIO_TOOL_SPEC, VIDEO_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "media_worker":           [IMAGE_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "audio_worker":           [AUDIO_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "digital_product_worker": [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "content_worker":         [FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "debug_worker":           [WEB_TOOL_SPEC, FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "market_research_worker": [WEB_TOOL_SPEC, FILE_TOOL_SPEC, TONY_INSIGHTS_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "outreach_worker":        [PLACES_TOOL_SPEC, WEB_TOOL_SPEC, EMAIL_TOOL_SPEC, SOCIAL_DM_TOOL_SPEC, FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, INBOX_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "marketing_worker":       [ETSY_TOOL_SPEC, FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "manager":                [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, FLAG_ISSUE_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "heavy_worker":           [FILE_TOOL_SPEC, CODE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "opportunity_worker":     [WEB_TOOL_SPEC, FILE_TOOL_SPEC, OPP_LOG_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
    "guard_worker":           [],
    "budget_worker":          [],
    "librarian":              [FILE_TOOL_SPEC],
    "builder":                [FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
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
    if not _pitch_is_alive():
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


def run_task(task: dict) -> dict:
    task_id = task["task_id"]
    role_id = route_task(task)

    if not acquire_lock(task_id, role_id):
        log.info("Task %s already locked — skipping", task_id)
        return {"skipped": True, "task_id": task_id}

    if is_budget_exceeded():
        release_lock(task_id)
        log.warning("Budget cap reached — skipping %s", task_id)
        return {"skipped": True, "task_id": task_id}

    pod = task.get("pod")
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


def run_cycle() -> None:
    if is_budget_exceeded():
        log.warning("Daily budget cap reached — skipping cycle.")
        return

    scan_tony_bridge()
    tasks = read_todo_tasks()
    if not tasks:
        log.info("No tasks in queue.")
        _maybe_spawn_planning_task()
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
    _sync_vault()


if __name__ == "__main__":
    run_cycle()
