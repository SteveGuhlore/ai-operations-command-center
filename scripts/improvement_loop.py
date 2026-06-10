#!/usr/bin/env python3
"""
Nightly improvement loop.
Reads today's vault sessions, calls Claude API, rewrites agent/*.md files that
underperformed, and commits the changes.

Run manually: python scripts/improvement_loop.py
Runs automatically: the runner's daily learning hook (runner/main.py `_maybe_run_learning`,
gated by `daily_learning_due(hour_after=2)`) invokes this once per day after 2 AM.
Rewrites are guarded by `_is_safe_rewrite` so an automated Flash rewrite can't strip a
load-bearing guardrail (it auto-commits, so unsafe rewrites would otherwise ship unsupervised).
"""
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
VAULT_DIR = ROOT / "vault"
AGENTS_DIR = ROOT / "agents"

# Only the agents that are actually running get reviewed. Outreach + Prospector
# (opportunity_worker) are disabled, so reviewing them would burn calls rewriting
# prompts for pipelines that never run. Tony-only focus as of 2026-06-04.
_AGENTS_TO_REVIEW = [
    "manager",
    "market_research_worker",
]

# Phrases that MUST survive any automated rewrite — these are load-bearing
# guardrails. This loop runs daily AND auto-commits, so a Flash rewrite that
# "summarizes" Tony's prompt and silently drops a critical rule would ship
# unsupervised. If a rewrite drops a protected phrase or shrinks the file too
# much, we reject it and keep the existing prompt.
_PROTECTED_PHRASES = {
    "market_research_worker": ["invoke", "verdict"],
}


def _is_safe_rewrite(agent_name: str, old: str, new: str) -> tuple[bool, str]:
    """Guard an automated prompt rewrite. Reject if the new content is suspiciously
    short (model truncated/summarized) or dropped a protected guardrail phrase."""
    if len(new) < len(old) * 0.6:
        return False, f"rewrite too short ({len(new)} vs {len(old)} chars)"
    low = new.lower()
    for phrase in _PROTECTED_PHRASES.get(agent_name, []):
        if phrase.lower() in old.lower() and phrase.lower() not in low:
            return False, f"dropped protected phrase '{phrase}'"
    return True, ""

_IMPROVEMENT_SYSTEM = """\
You are the improvement engine for the AI Operations Command Center.
Your job: analyze today's agent session data and improve agent prompt files that underperformed.

Rules:
- Only rewrite agents that produced poor output or hit errors today.
- Preserve each agent's core role — only tune the instructions and style.
- If an agent performed well, output NO_CHANGE.
- Be specific: if Spark wrote weak hooks, improve the hook-writing instructions.
- Output valid markdown that fully replaces the existing agent file.

Output format — use this exact structure for EVERY agent you review:

AGENT: <agent_name>
CHANGED
<full new markdown content for agents/<agent_name>.md>
END_AGENT

or if no change needed:

AGENT: <agent_name>
NO_CHANGE
END_AGENT

After all agent blocks, write a one-paragraph plain-text summary of what you changed and why.
"""


def _read_recent_sessions() -> str:
    """Concatenated session text for the most recent day that HAS sessions. The hook runs at ~2 AM
    when today's session dir is still empty, so reading 'today' skipped review every night (the
    silent-since-June-5 bug). Scan newest-first and take the first non-empty day — that's yesterday
    at 2 AM, or today if run midday. Look back a bounded window so a quiet stretch can't reach back
    forever."""
    base = VAULT_DIR / "sessions"
    if not base.exists():
        return ""
    days = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True)
    for d in days[:7]:
        parts = [f.read_text(encoding="utf-8") for f in sorted(d.glob("*.md"))]
        if parts:
            log.info("Reviewing %d session(s) from %s", len(parts), d.name)
            return "\n\n---\n\n".join(parts)
    return ""


def _read_workspace_context() -> str:
    parts = []
    for name in ("AGENTS.md", "SOUL.md", "TOOLS.md"):
        f = VAULT_DIR / name
        if f.exists():
            parts.append(f"## {name}\n{f.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def _parse_updates(response_text: str) -> tuple[dict[str, str], str]:
    """Parse Claude's response into {agent_name: new_content} and a summary string."""
    updates: dict[str, str] = {}
    summary = ""

    blocks = response_text.split("AGENT: ")
    for block in blocks[1:]:
        lines = block.strip().split("\n")
        agent_name = lines[0].strip()
        rest = "\n".join(lines[1:])
        end_idx = rest.find("\nEND_AGENT")
        if end_idx == -1:
            continue
        body = rest[:end_idx].strip()
        if body.startswith("NO_CHANGE"):
            continue
        # Strip the "CHANGED" sentinel line if present
        body_lines = body.split("\n")
        if body_lines and body_lines[0].strip() == "CHANGED":
            body = "\n".join(body_lines[1:]).strip()
        if body:
            updates[agent_name] = body

    # Everything after the last END_AGENT is the summary
    last_end = response_text.rfind("END_AGENT")
    if last_end != -1:
        summary = response_text[last_end + len("END_AGENT"):].strip()

    return updates, summary


def _commit_improvements(agents_updated: list[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    msg = f"improvement-loop: {today} — {len(agents_updated)} agent(s) updated: {', '.join(agents_updated)}"
    subprocess.run(["git", "add", "agents/"], cwd=ROOT, check=False, capture_output=True)
    result = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        log.info("Committed: %s", msg)
    else:
        log.warning("Git commit output: %s", result.stdout + result.stderr)


def _write_improvement_summary(summary: str, agents_updated: list[str]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    out = VAULT_DIR / "learnings" / f"{today}-overnight.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"# Improvement Loop — {today}\n"
        f"Agents updated: {', '.join(agents_updated) if agents_updated else 'none'}\n\n"
        f"{summary}\n"
    )
    try:
        out.write_text(content, encoding="utf-8")
        log.info("Summary written to %s", out)
    except OSError as exc:
        log.error("Could not write improvement summary: %s", exc)


def run() -> None:
    log.info("Improvement loop starting")

    vault_today = _read_recent_sessions()
    if not vault_today:
        log.info("No session data in the last 7 days — skipping")
        return

    workspace_ctx = _read_workspace_context()
    agent_contents = {
        name: (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        for name in _AGENTS_TO_REVIEW
        if (AGENTS_DIR / f"{name}.md").exists()
    }

    user_prompt = (
        f"## Today's Session Data\n{vault_today}\n\n"
        f"## Workspace Context\n{workspace_ctx}\n\n"
        f"## Current Agent Files\n"
        + "\n".join(f"### {n}\n{c}" for n, c in agent_contents.items())
    )

    client = OpenAI(
        api_key=os.environ.get("GOOGLE_AI_API_KEY", ""),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash",
            max_tokens=8192,
            messages=[
                {"role": "system", "content": _IMPROVEMENT_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        log.error("Gemini API call failed: %s", exc)
        return

    output = response.choices[0].message.content or ""
    if not output:
        log.error("Empty response from Gemini")
        return
    log.info("Improvement response received (%d chars)", len(output))

    updates, summary = _parse_updates(output)
    agents_updated = []

    rejected = []
    for agent_name, new_content in updates.items():
        if agent_name not in agent_contents:
            log.warning("Skipping unknown agent: %s", agent_name)
            continue
        ok, why = _is_safe_rewrite(agent_name, agent_contents[agent_name], new_content)
        if not ok:
            log.warning("REJECTED rewrite of agents/%s.md — %s (keeping existing prompt)", agent_name, why)
            rejected.append(f"{agent_name} ({why})")
            continue
        (AGENTS_DIR / f"{agent_name}.md").write_text(new_content, encoding="utf-8")
        log.info("Updated agents/%s.md", agent_name)
        agents_updated.append(agent_name)
    if rejected:
        summary = (summary + "\n\n" if summary else "") + "REJECTED (unsafe): " + "; ".join(rejected)

    if agents_updated:
        _commit_improvements(agents_updated)

    _write_improvement_summary(summary, agents_updated)
    log.info("Improvement loop complete — updated: %s", agents_updated or "none")


if __name__ == "__main__":
    run()
