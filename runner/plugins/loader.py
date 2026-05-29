import re
from pathlib import Path

# Plugins/skills live under the Claude Code plugin cache. The official marketplace is in
# claude-plugins-official/; community skill repos (taste-skill, interface-design,
# agent-skills, designer-skills, ecc, impeccable, ui-ux-pro-max-skill, …) are cloned
# directly under the cache root. A skill resolves by scanning its repo for
# skills/<skill>/SKILL.md (or <skill>.md), so all of these layouts work:
#   claude-plugins-official/<plugin>/<ver>/skills/<skill>/SKILL.md
#   <repo>/<repo>/<ver>/.agents/skills/<skill>/SKILL.md        (ecc)
#   <repo>/.claude/skills/<skill>/SKILL.md                     (interface-design)
#   <repo>/skills/<skill>/SKILL.md                             (taste-skill, agent-skills)
CACHE_ROOT = Path.home() / ".claude" / "plugins" / "cache"
PLUGINS_CACHE = CACHE_ROOT / "claude-plugins-official"  # kept for back-compat (tests monkeypatch this)

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

# Clay's (builder) design library. The CORE skills are injected in FULL on every build;
# the rest of the installed design skills are offered as a compact MENU so Clay has options
# to recall and apply, and the design-memory loop (scripts/design_synthesis.py) merges what
# actually works into Clay's own evolving style over time.
BUILDER_CORE_SKILLS: list[tuple[str, str]] = [
    ("frontend-design", "frontend-design"),       # Anthropic official design skill
    ("taste-skill", "taste-skill"),               # overall design taste
    ("interface-design", "interface-design"),     # interface craft + consistency
    ("agent-skills", "web-design-guidelines"),    # Vercel web design guidelines
    ("ecc", "brand-voice"),                       # brand voice / UX writing
    ("ecc", "frontend-patterns"),                 # frontend implementation patterns
]

# Repos scanned to build the design-skill MENU (dir names under the cache root).
# ecc is deliberately excluded — it is a 300+ skill general-purpose plugin, not a design
# repo, so auto-scanning it would flood the menu with irrelevant engineering skills. Its
# genuine design skills are pulled in explicitly via BUILDER_CORE_SKILLS instead.
DESIGN_SKILL_REPOS = [
    "claude-plugins-official/frontend-design",
    "taste-skill", "interface-design", "agent-skills",
    "designer-skills", "impeccable", "ui-ux-pro-max-skill",
]

_FM_DESC = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def _find_skill_file(plugin: str, skill: str) -> Path | None:
    """Locate skills/<skill>/SKILL.md (or <skill>.md) inside a plugin's tree. Searches the
    official cache first (so tests that monkeypatch PLUGINS_CACHE keep working), then the
    cache root for community repos. Localized docs/ copies are ignored."""
    roots = [PLUGINS_CACHE]
    if PLUGINS_CACHE.parent != PLUGINS_CACHE:
        roots.append(PLUGINS_CACHE.parent)
    for root in roots:
        base = root / plugin
        if not base.exists():
            continue
        for fn in (f"{skill}.md", "SKILL.md"):
            cands = [
                p for p in base.rglob(fn)
                if p.parent.name == skill and p.parent.parent.name == "skills"
                and "docs" not in p.parts
            ]
            if cands:
                return sorted(cands, reverse=True)[0]
    return None


def load_skill(plugin: str, skill: str) -> str:
    path = _find_skill_file(plugin, skill)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


_design_menu_cache: list[tuple[str, str]] | None = None


def discover_design_skills() -> list[tuple[str, str]]:
    """Every design skill installed across DESIGN_SKILL_REPOS, as (name, description).
    Computed once per process. Localized docs/ copies and duplicates are skipped."""
    global _design_menu_cache
    if _design_menu_cache is not None:
        return _design_menu_cache
    found: dict[str, str] = {}
    for repo in DESIGN_SKILL_REPOS:
        base = CACHE_ROOT / repo
        if not base.exists():
            continue
        try:
            skill_files = list(base.rglob("SKILL.md"))
        except OSError:
            continue
        for p in skill_files:
            if "docs" in p.parts or p.parent.parent.name != "skills":
                continue
            name = p.parent.name
            if name in found:
                continue
            try:
                head = p.read_text(encoding="utf-8", errors="ignore")[:800]
            except OSError:
                continue
            m = _FM_DESC.search(head)
            desc = (m.group(1).strip().strip('"').strip("'") if m else "")[:160]
            found[name] = desc
    _design_menu_cache = sorted(found.items())
    return _design_menu_cache


def build_design_skill_menu() -> str:
    skills = discover_design_skills()
    if not skills:
        return ""
    return "\n".join(f"- **{n}** — {d}" if d else f"- **{n}**" for n, d in skills)


def _build_builder_skills_prompt() -> str:
    parts = []
    for plugin, skill in BUILDER_CORE_SKILLS:
        content = load_skill(plugin, skill)
        if content:
            parts.append(f"--- SKILL: {skill} ---\n{content}")
    menu = build_design_skill_menu()
    if menu:
        parts.append(
            "--- DESIGN SKILL LIBRARY (your options) ---\n"
            "The core design skills above are loaded in full. The skills below are also installed "
            "and available to you — recall and apply their principles when a build calls for them "
            "(e.g. a brutalist hero, a minimalist pricing page, a bold landing). Note in `write_memory` "
            "which skills you drew on and what worked, so the design-memory loop can merge them into "
            "your own evolving style:\n\n" + menu
        )
    return "\n\n".join(parts)


def build_agent_skills_prompt(role_id: str) -> str:
    if role_id == "builder":
        return _build_builder_skills_prompt()
    parts = []
    for plugin, skill in AGENT_SKILLS.get(role_id, []):
        content = load_skill(plugin, skill)
        if content:
            parts.append(f"--- SKILL: {skill} ---\n{content}")
    return "\n\n".join(parts)
