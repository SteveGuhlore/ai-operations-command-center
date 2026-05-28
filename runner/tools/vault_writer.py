import logging
from datetime import datetime
from pathlib import Path

VAULT_DIR = Path(__file__).parent.parent.parent / "vault"

_log = logging.getLogger(__name__)

_ROLE_TAGS = {
    "market_research_worker": ["tony-stocks", "research"],
    "manager":                ["atlas", "planning"],
    "debug_worker":           ["scout", "research"],
    "heavy_worker":           ["forge", "analysis"],
    "content_worker":         ["muse", "content"],
    "social_media_worker":    ["spark", "social"],
    "digital_product_worker": ["maker", "products"],
    "marketing_worker":       ["market", "marketing"],
    "media_worker":           ["frame", "media"],
    "audio_worker":           ["echo", "audio"],
    "outreach_worker":        ["pitch", "outreach"],
    "librarian":              ["sage", "memory"],
}

_ROLE_FALLBACK_SUMMARY = {
    "outreach_worker":        "Outreach run completed",
    "social_media_worker":    "Video content produced",
    "digital_product_worker": "Digital product created",
    "market_research_worker": "Market research completed",
    "manager":                "Planning completed",
    "marketing_worker":       "Marketing copy produced",
    "content_worker":         "Content drafted",
    "debug_worker":           "Analysis completed",
    "media_worker":           "Media assets generated",
    "audio_worker":           "Audio generated",
    "heavy_worker":           "Implementation completed",
    "librarian":              "Memory synthesis completed",
}


def _extract_summary(output: str, role_id: str) -> str:
    skip = ("#", "---", "|", "```", "**Agent", "**Token", "**Error", "**Date", "**Status")
    for line in output.split("\n"):
        line = line.strip()
        if len(line) > 25 and not any(line.startswith(p) for p in skip):
            return line[:120]
    return _ROLE_FALLBACK_SUMMARY.get(role_id, f"{role_id} task completed")


def write_vault_session(task_id: str, role_id: str, result: dict, *, vault_dir=None) -> None:
    base = Path(vault_dir) if vault_dir else VAULT_DIR
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        session_dir = base / "sessions" / today
        session_dir.mkdir(parents=True, exist_ok=True)

        status = "failed" if "error" in result else "done"
        output = str(result.get("output", ""))
        safe_id = task_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        summary = _extract_summary(output if status == "done" else result.get("error", ""), role_id)

        tags = ["session", status] + _ROLE_TAGS.get(role_id, [role_id])
        tag_str = "[" + ", ".join(tags) + "]"

        content = (
            f"---\n"
            f"tags: {tag_str}\n"
            f"agent: {role_id}\n"
            f"task_id: {task_id}\n"
            f"date: {today}\n"
            f"status: {status}\n"
            f"summary: {summary}\n"
            f"cost_usd: {result.get('cost_usd', 0.0):.4f}\n"
            f"---\n\n"
            f"# {task_id}\n\n"
            f"**Agent:** {role_id} · **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
            f"**Status:** {status} · **Cost:** ${result.get('cost_usd', 0.0):.4f}\n"
            f"**Tokens:** {result.get('input_tokens', 0)} in / {result.get('output_tokens', 0)} out\n"
            f"**Errors:** {result.get('error', 'none')}\n\n"
            f"Part of [[sessions/index]] · [[index]]\n\n"
            f"## Output\n\n"
            f"{output}\n"
        )

        (session_dir / f"{safe_id}.md").write_text(content, encoding="utf-8")
    except OSError as exc:
        _log.warning("vault_writer: could not write session for %s: %s", task_id, exc)
