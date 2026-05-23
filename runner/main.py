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
from runner.ledger.budget import is_budget_exceeded
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
from runner.tools.vault_writer import write_vault_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODELS: dict[str, str] = {
    "manager":                "anthropic/claude-sonnet-4-6",  # atlas planning; opus was 25x pricier
    "heavy_worker":           "moonshotai/kimi-k2.5",
    "debug_worker":           "minimax/minimax-m2.5",
    "content_worker":         "minimax/minimax-m2.5",
    "media_worker":           "moonshotai/kimi-k2.5",
    "audio_worker":           "minimax/minimax-m2.5",
    "guard_worker":           "minimax/minimax-m2.5",
    "budget_worker":          "minimax/minimax-m2.5",
    "digital_product_worker": "moonshotai/kimi-k2.5",
    "marketing_worker":       "minimax/minimax-m2.5",
    "social_media_worker":    "moonshotai/kimi-k2.5",
}

MAX_CONCURRENT = 4
LOW_WATER_MARK = 3  # spawn Atlas planning task when todo queue drops below this

# Tools each role is allowed to call
ROLE_TOOLS: dict[str, list[dict]] = {
    "social_media_worker":    [TOOL_SPEC_SAVE, IMAGE_TOOL_SPEC, AUDIO_TOOL_SPEC, VIDEO_TOOL_SPEC],
    "media_worker":           [IMAGE_TOOL_SPEC, FILE_TOOL_SPEC],
    "audio_worker":           [AUDIO_TOOL_SPEC, FILE_TOOL_SPEC],
    "digital_product_worker": [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC],
    "content_worker":         [FILE_TOOL_SPEC],
    "debug_worker":           [WEB_TOOL_SPEC, FILE_TOOL_SPEC],
    "marketing_worker":       [ETSY_TOOL_SPEC, FILE_TOOL_SPEC],
    "manager":                [FILE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC],
    "heavy_worker":           [FILE_TOOL_SPEC],
    "guard_worker":           [],
    "budget_worker":          [],
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

The task queue is running low. Use the `create_task` tool to spawn **6–8 new revenue-generating tasks** right now.

## Brand Context

- **Shop:** ThePromptVaultUS — AI prompt packs for creators, freelancers, and small business owners
- **Products:** PDF prompt packs, $6–$14, instant download
- **Social:** TikTok (manual upload), Instagram Reels (auto), Facebook Reels (auto), YouTube Shorts (auto)
- **Revenue model:** Views/CPM from organic video + TikTok Shop affiliate commissions + digital product sales

## Available Agents

| Agent | role_id | What they do |
|---|---|---|
| Spark | social_media_worker | Writes scripts, generates audio + images + assembles MP4 — full video pipeline |
| Muse | content_worker | Captions, written content, blog-style posts |
| Maker | digital_product_worker | Creates PDF prompt packs |
| Market | marketing_worker | Offer positioning, hooks, listing copy |
| Frame | media_worker | Standalone image generation |
| Echo | audio_worker | Standalone audio/voiceover generation |
| Scout | debug_worker | Reports, validations |

## Task Priorities

**Always spawn at least 3 video_production tasks for Spark.** These are the highest-ROI tasks (each MP4 can generate views/CPM across 4 platforms).

Good video topic ideas for Spark:
- "5 ChatGPT prompts that save freelancers 10 hours a week"
- "The one prompt that writes all my emails in 30 seconds"
- "POV: You finally stopped undercharging (AI helped)"
- "How I use AI to batch a month of content in one day"
- "Rate my ChatGPT setup vs. a beginner's"
- "TikTok Shop finds for creators who use AI"
- "Stop writing captions from scratch — use this prompt"
- "The AI workflow that replaced my content team"

Good Maker tasks: Create a new prompt pack PDF (30–50 prompts) on a specific topic (email marketing prompts, freelancer pricing prompts, content repurposing prompts, etc.)

Good Market tasks: Write Etsy listing copy + title + tags for a specific prompt pack product.

## Already Done (don't duplicate these)

{done_summary}

## Instructions

Call `create_task` once per task. Spawn 6–8 tasks total. Prefer high-priority video production tasks.
For video_production tasks assigned to social_media_worker, write a detailed brief including:
- The hook (first 1–2 seconds)
- Target audience
- Key message/tip to deliver
- CTA to use
- Suggested voice: nova (energetic) or onyx (deep)

Do not stop until you have called create_task at least 6 times.
"""


def _maybe_spawn_planning_task() -> None:
    remaining = read_todo_tasks()
    has_planning = any(t.get("task_type") in ("planning",) for t in remaining)
    if len(remaining) < LOW_WATER_MARK and not has_planning:
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
        log.info(
            "Queue low (%d tasks remaining) — spawned Atlas planning task: %s",
            len(remaining),
            result.get("task_id"),
        )


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

    try:
        update_agent_state(role_id, "working", task_id)
        move_task(task_id, "todo", "in_progress")

        model = MODELS.get(role_id, "claude-haiku-4-5")
        tools = ROLE_TOOLS.get(role_id, [])
        agent = AgentBase(role_id, model, build_system_prompt(role_id), tools=tools)
        result = agent.run(task)

        write_task_output(task_id, result["output"], "in_progress")
        write_vault_session(task_id, role_id, result)
        move_task(task_id, "in_progress", "done")
        update_agent_state(role_id, "idle", "", f"completed {task_id}")
        log.info("%s completed %s ($%.4f)", role_id, task_id, result["cost_usd"])
        return result

    except Exception as exc:
        log.error("%s failed %s: %s", role_id, task_id, exc)
        write_vault_session(task_id, role_id, {"error": str(exc)})
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = [executor.submit(run_task, t) for t in batch]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                log.error("Unhandled task error: %s", exc)

    _maybe_spawn_planning_task()
    _sync_vault()


if __name__ == "__main__":
    run_cycle()
