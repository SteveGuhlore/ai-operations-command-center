from pathlib import Path
from runner.config import load_agents
from runner.plugins.loader import build_agent_skills_prompt
from runner.tools.vault_memory import load_agent_memory

BASE_DIR = Path(__file__).parent.parent.parent

_ROLE_MD_FILES = {
    "manager":                "agents/manager.md",
    "heavy_worker":           "agents/heavy_worker.md",
    "debug_worker":           "agents/debug_worker.md",
    "content_worker":         "agents/content_worker.md",
    "media_worker":           "agents/media_worker.md",
    "audio_worker":           "agents/audio_worker.md",
    "guard_worker":           "agents/guard_worker.md",
    "budget_worker":          "agents/budget_worker.md",
    "digital_product_worker": "agents/digital_product_worker.md",
    "marketing_worker":       "agents/marketing_worker.md",
    "market_research_worker": "agents/market_research_worker.md",
    "social_media_worker":    "agents/social_media_worker.md",
    "outreach_worker":        "agents/outreach_worker.md",
    "librarian":              "agents/librarian.md",
    "builder":                "agents/builder.md",
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

    if role_id == "outreach_worker":
        parts.append(
            "\n\nCRITICAL RULES — NON-NEGOTIABLE:\n"
            "1. You MUST call file_editor (action=append) to add new prospects to vault/outreach/crm.md. "
            "NEVER use action=write on the CRM — it overwrites and destroys existing rows. "
            "Append only new pipe-delimited rows, one per line. Do NOT read the file first unless checking for dupes. "
            "Skipping the CRM append is a failure.\n"
            "2. STATUS DISCIPLINE: When adding a NEW prospect where you only found a phone number (no actual "
            "contact was made), status MUST be `call_queued`. NEVER write `interested`, `replied`, `closed`, "
            "or `no_interest` for a prospect you have not actually contacted. Those statuses are only valid "
            "after a real human interaction.\n"
            "3. DEDUP: Before writing, compare every new prospect name against the existing CRM rows. If the "
            "business name already appears (any status), SKIP IT — do not add a duplicate row.\n"
            "4. NO WEB_RESEARCH FOR CONTACT LOOKUP: web_research hits CAPTCHA on every contact lookup and "
            "will consume your entire time budget. Use ONLY what find_prospects returns. Phone number alone "
            "is sufficient — set status to call_queued and move on. Never call web_research to find emails."
        )

    skills_content = build_agent_skills_prompt(role_id)
    if skills_content:
        parts.append(f"\n## Workflow Skills\n\n{skills_content}")

    memory = load_agent_memory(role_id)
    if memory:
        parts.append(f"\n---\n\n{memory}")

    return "\n\n".join(parts)
