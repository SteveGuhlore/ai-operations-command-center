from pathlib import Path

PLUGINS_CACHE = Path.home() / ".claude" / "plugins" / "cache" / "claude-plugins-official"

AGENT_SKILLS: dict[str, list[tuple[str, str]]] = {
    "manager":                [("superpowers", "dispatching-parallel-agents")],
    "heavy_worker":           [("feature-dev", "feature-dev"), ("superpowers", "test-driven-development")],
    "debug_worker":           [("superpowers", "systematic-debugging"), ("code-review", "code-review")],
    "content_worker":         [],
    "media_worker":           [],
    "audio_worker":           [],
    "guard_worker":           [],
    "budget_worker":          [],
    "digital_product_worker": [("feature-dev", "feature-dev")],
    "marketing_worker":       [],
}


def _find_skill_file(plugin: str, skill: str) -> Path | None:
    plugin_dir = PLUGINS_CACHE / plugin
    if not plugin_dir.exists():
        return None
    for version_dir in sorted(plugin_dir.iterdir(), reverse=True):
        candidate = version_dir / "skills" / skill / f"{skill}.md"
        if candidate.exists():
            return candidate
    return None


def load_skill(plugin: str, skill: str) -> str:
    path = _find_skill_file(plugin, skill)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_agent_skills_prompt(role_id: str) -> str:
    skills = AGENT_SKILLS.get(role_id, [])
    parts = []
    for plugin, skill in skills:
        content = load_skill(plugin, skill)
        if content:
            parts.append(f"--- SKILL: {skill} ---\n{content}")
    return "\n\n".join(parts)
