import re
from datetime import datetime
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"

VALID_AGENTS = [
    "manager",
    "social_media_worker", "content_worker", "digital_product_worker",
    "marketing_worker", "media_worker", "audio_worker",
    "heavy_worker", "debug_worker", "budget_worker", "guard_worker",
]


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
                    "short_form_video_pod", "lead_gen_pod", "management", "general",
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
