from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
AGENTS_MEMORY_DIR = BASE_DIR / "vault" / "agents"

WRITE_MEMORY_TOOL_SPEC = {
    "name": "write_memory",
    "description": (
        "Log a learning, success, failure, or observed pattern to your persistent memory vault. "
        "Call this during or at the end of your run to capture what worked, what failed, and rules you discovered. "
        "These entries are injected into your context on future runs so you improve over time."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "role_id": {
                "type": "string",
                "description": "Your agent role ID — matches 'Your role:' in your system prompt (e.g. outreach_worker).",
            },
            "entry_type": {
                "type": "string",
                "enum": ["success", "failure", "pattern", "metric"],
                "description": (
                    "success=what worked well, "
                    "failure=what failed and why, "
                    "pattern=recurring observation, "
                    "metric=numerical outcome (rates, counts, etc.)"
                ),
            },
            "content": {
                "type": "string",
                "description": (
                    "What you learned. Be specific: include business types, cities, methods, "
                    "outcomes, error messages, and any rules discovered."
                ),
            },
        },
        "required": ["role_id", "entry_type", "content"],
    },
}


def _agent_dir(role_id: str) -> Path:
    d = AGENTS_MEMORY_DIR / role_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _prepend_entry(filepath: Path, entry: str) -> None:
    existing = filepath.read_text(encoding="utf-8") if filepath.exists() else "# Memory Log\n"
    nl = existing.find("\n")
    if nl == -1:
        filepath.write_text(existing + "\n" + entry + "\n", encoding="utf-8")
    else:
        filepath.write_text(existing[: nl + 1] + "\n" + entry + "\n" + existing[nl + 1 :], encoding="utf-8")


def write_memory(role_id: str, entry_type: str, content: str) -> dict:
    """Tool function — agents call this mid-run to log learnings."""
    try:
        memory_file = _agent_dir(role_id) / "memory.md"
        date = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"## {date} — {entry_type}\n{content.strip()}"
        _prepend_entry(memory_file, entry)
        return {"saved": True, "role_id": role_id, "entry_type": entry_type}
    except Exception as exc:
        return {"error": str(exc)}


def auto_write_task_memory(
    role_id: str, task_id: str, task_type: str, outcome: str, summary: str
) -> None:
    """Called by main.py after every task — no LLM needed, structured log only."""
    try:
        # A run that made no tool calls produced nothing real — never record it as a
        # success, or agents learn that doing nothing wins. Downgrade to no-op.
        if outcome == "success" and "(no tool calls made this run)" in (summary or ""):
            outcome = "noop"
        if outcome == "success" and "ALL_TOOLS_ERRORED" in (summary or ""):
            outcome = "failure"
        memory_file = _agent_dir(role_id) / "memory.md"
        date = datetime.now().strftime("%Y-%m-%d")
        entry = f"## {date} — auto — {outcome}\nTask: {task_id} | type: {task_type}\n{summary[:400].strip()}"
        _prepend_entry(memory_file, entry)
    except Exception:
        pass  # memory write failure must never break a task run


def load_agent_memory(role_id: str) -> str:
    """Called by prompts.py — injects memory into every agent's system prompt."""
    agent_dir = AGENTS_MEMORY_DIR / role_id
    if not agent_dir.exists():
        return ""

    parts = []

    rules_file = agent_dir / "learned_rules.md"
    if rules_file.exists():
        rules = rules_file.read_text(encoding="utf-8").strip()
        if rules and "_No rules distilled yet_" not in rules and len(rules) > 40:
            parts.append(f"## Your Learned Rules\n\n{rules}")

    memory_file = agent_dir / "memory.md"
    if memory_file.exists():
        lines = memory_file.read_text(encoding="utf-8").strip().split("\n")
        content_lines = [l for l in lines if not l.startswith("# Memory")]
        recent = "\n".join(content_lines[:60]).strip()
        if recent:
            parts.append(f"## Your Recent Run Log\n\n{recent}")

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
