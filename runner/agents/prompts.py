from pathlib import Path
from runner.config import load_agents
from runner.plugins.loader import build_agent_skills_prompt

BASE_DIR = Path(__file__).parent.parent.parent

_ROLE_MD_FILES = {
    "manager": "agents/manager.md",
    "heavy_worker": "agents/heavy_worker.md",
    "debug_worker": "agents/debug_worker.md",
}


def _load_agent_md(role_id: str) -> str:
    filename = _ROLE_MD_FILES.get(role_id)
    if not filename:
        return ""
    path = BASE_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _get_agent_config(role_id: str) -> dict:
    agents = load_agents()
    for agent in agents["agents"]:
        if agent["role_id"] == role_id:
            return agent
    return {}


def build_system_prompt(role_id: str) -> str:
    config = _get_agent_config(role_id)
    md = _load_agent_md(role_id)

    parts = []
    if md:
        parts.append(md)

    display_name = config.get("display_name", role_id)
    purpose = config.get("purpose", "")
    allowed_types = config.get("allowed_task_types", [])

    parts.append(f"Your role: {role_id}")
    parts.append(f"Display name: {display_name}")
    if purpose:
        parts.append(f"Purpose: {purpose}")
    if allowed_types:
        parts.append(f"Allowed task types: {', '.join(allowed_types)}")

    parts.append(
        "\nComplete the assigned task fully. Write your output clearly and concisely. "
        "Begin immediately — do not explain what you are about to do, just do it."
    )

    skills_content = build_agent_skills_prompt(role_id)
    if skills_content:
        parts.append(f"\n## Workflow Skills\n\n{skills_content}")

    return "\n\n".join(parts)
