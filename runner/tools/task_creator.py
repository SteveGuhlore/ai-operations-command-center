import logging
import re
from datetime import datetime
from pathlib import Path

from runner.scheduler.spawn_gate import record_spawn, spawn_allowed

log = logging.getLogger(__name__)

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"
BLOCKED_LOG = TASKS_DIR.parent / "blocked-tasks.log"

VALID_AGENTS = [
    "manager",
    "social_media_worker", "content_worker", "digital_product_worker",
    "marketing_worker", "media_worker", "audio_worker",
    "heavy_worker", "debug_worker", "budget_worker", "guard_worker",
    "market_research_worker", "outreach_worker", "builder", "librarian",
]

# Self-perpetuating repair loop: agents kept spawning audit/revise tasks against
# the read_inbox tool every cycle (50+ in 36h) without ever fixing anything.
# Prompt directives didn't hold, so block these at the spawn point regardless of
# which agent/model emits them. Outreach (pitch-continuous-outreach) is unaffected:
# it has no "read inbox" subject and no meta-work verb.
_META_VERB = r"(audit|revis|refin|confirm|verif|inspect|investigat|fix|correct|accura|misclass|misiden|false[\s_-]*posit|incorrect|root[\s_-]*cause)"
_INBOX_SUBJECT = r"read[\s_-]*inbox|inbox[\s_-]*tool|inbox[\s_-]*reader"
_LOOP_BLOCK_RE = re.compile(_META_VERB, re.IGNORECASE)
_INBOX_RE = re.compile(_INBOX_SUBJECT, re.IGNORECASE)


def _is_blocked_loop_task(title: str, body: str) -> bool:
    haystack = f"{title}\n{body[:500]}"
    return bool(_INBOX_RE.search(haystack) and _LOOP_BLOCK_RE.search(haystack))


def _log_blocked(title: str, assigned_agent: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}\tNEEDS_HUMAN\t{assigned_agent}\t{title}\n"
    try:
        with BLOCKED_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        log.error("Could not write blocked-tasks log: %s", exc)
    log.warning("Blocked read_inbox repair-loop task from %s: %s", assigned_agent, title)


def _has_pending_task(assigned_agent: str, task_type: str) -> bool:
    for folder in ("todo",):
        d = TASKS_DIR / folder
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                if f"assigned_agent: {assigned_agent}" in content and f"task_type: {task_type}" in content:
                    return True
            except OSError:
                pass
    return False


def create_task(
    title: str,
    body: str,
    assigned_agent: str,
    task_type: str,
    pod: str = "general",
    priority: str = "normal",
    task_id: str = "",
) -> dict:
    if assigned_agent not in VALID_AGENTS:
        return {"error": f"Unknown agent: {assigned_agent}. Valid: {VALID_AGENTS}"}

    if _is_blocked_loop_task(title, body):
        _log_blocked(title, assigned_agent)
        return {"skipped": True, "reason": "read_inbox audit/revise tasks are disabled — logged to blocked-tasks.log for human review. Do not retry; this is intentional."}

    if _has_pending_task(assigned_agent, task_type):
        return {"skipped": True, "reason": f"A pending {task_type} task for {assigned_agent} already exists — not creating a duplicate."}

    allowed, reason = spawn_allowed(assigned_agent, task_type)
    if not allowed:
        log.info("Spawn cadence gate: %s", reason)
        return {"skipped": True, "reason": reason}

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    auto_id = not task_id
    if auto_id:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:30].strip("-")
        task_id = f"AUTO-{ts}-{slug}"

    todo_dir = TASKS_DIR / "todo"
    todo_dir.mkdir(parents=True, exist_ok=True)

    if auto_id:
        # task_id already encodes the title slug — no need to repeat it
        filename = f"{task_id}.md"
    else:
        file_slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:50].strip("-")
        filename = f"{task_id}-{file_slug}.md"

    content = (
        f"---\n"
        f"task_id: {task_id}\n"
        f"assigned_agent: {assigned_agent}\n"
        f"status: todo\n"
        f"priority: {priority}\n"
        f"pod: {pod}\n"
        f"task_type: {task_type}\n"
        f"created_at: {ts}\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{body.strip()}\n"
    )

    path = todo_dir / filename
    path.write_text(content, encoding="utf-8")
    record_spawn(assigned_agent, task_type)
    return {"success": True, "task_id": task_id, "path": str(path)}


TOOL_SPEC = {
    "name": "create_task",
    "description": (
        "Create a new task file in workspace/tasks/todo/ so another agent can pick it up "
        "in the next runner cycle. Use this to spawn follow-up work for any revenue pod."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short descriptive title for the task (5-10 words).",
            },
            "body": {
                "type": "string",
                "description": (
                    "Full task instructions in markdown. Be specific: include the goal, "
                    "deliverables, any constraints, and the exact tool calls expected."
                ),
            },
            "assigned_agent": {
                "type": "string",
                "description": "Role ID of the agent who should execute this task.",
                "enum": VALID_AGENTS,
            },
            "task_type": {
                "type": "string",
                "description": (
                    "Task category matching the agent's allowed_task_types. Examples: "
                    "video_production, guide_creation, content_drafting, affiliate_research, "
                    "tiktok_shop_promo, hook_writing, caption_pack, product_research."
                ),
            },
            "pod": {
                "type": "string",
                "description": "Revenue pod this task belongs to.",
                "enum": [
                    "social_media_pod", "digital_products_pod", "affiliate_pod",
                    "short_form_video_pod", "lead_gen_pod", "local_outreach_pod",
                    "management", "general",
                ],
            },
            "priority": {
                "type": "string",
                "enum": ["high", "normal", "low"],
                "default": "normal",
                "description": "Execution priority. High tasks run first.",
            },
            "task_id": {
                "type": "string",
                "description": (
                    "Optional custom ID like POD-SOC-005 or POD-DIG-004. "
                    "Auto-generated with timestamp if omitted."
                ),
            },
        },
        "required": ["title", "body", "assigned_agent", "task_type"],
    },
}
