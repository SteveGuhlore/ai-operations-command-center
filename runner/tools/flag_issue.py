"""Cross-agent triage tool.

Any agent can call `flag_issue` when it detects a bug, broken workflow, missing
data, or unexpected behavior. It spawns a high-priority debug task for Scout
(debug_worker) so problems get triaged automatically instead of buried in agent
output.
"""
from runner.tools.task_creator import create_task

SEVERITY_PRIORITY = {
    "critical": "high",
    "high": "high",
    "medium": "normal",
    "low": "low",
}


def flag_issue(
    title: str,
    description: str,
    severity: str = "medium",
    reporter: str = "unknown",
    suggested_fix: str = "",
) -> dict:
    severity = severity.lower().strip()
    priority = SEVERITY_PRIORITY.get(severity, "normal")

    body = (
        f"## Reported By\n"
        f"{reporter}\n\n"
        f"## Severity\n"
        f"{severity}\n\n"
        f"## Issue Description\n"
        f"{description.strip()}\n\n"
        f"## Suggested Fix (from reporter)\n"
        f"{suggested_fix.strip() if suggested_fix else '(none provided)'}\n\n"
        f"## Your Job (Scout)\n"
        f"1. Read the description above and confirm the bug exists by checking the relevant files or vault state.\n"
        f"2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).\n"
        f"3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.\n"
        f"4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.\n"
    )

    return create_task(
        title=f"Scout audit: {title}",
        body=body,
        assigned_agent="debug_worker",
        task_type="debugging",
        pod="management",
        priority=priority,
    )


TOOL_SPEC = {
    "name": "flag_issue",
    "description": (
        "Flag a bug, broken workflow, missing data, or unexpected behavior. "
        "This spawns a high-priority debug task for Scout to investigate and route the fix. "
        "Call this whenever you notice something wrong DURING your normal workflow — do NOT "
        "swallow the issue silently in your output. Examples: CRM has bad data, a tool errored "
        "in a way that suggests config drift, an instruction in your prompt contradicts another, "
        "a task body is malformed, an integration is missing keys you'd expect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "One-line summary of the issue (5-10 words). Becomes part of the Scout task title.",
            },
            "description": {
                "type": "string",
                "description": (
                    "What you observed, where, and why it's a problem. Include file paths, "
                    "task IDs, CRM rows, or any other concrete pointer Scout can use to reproduce."
                ),
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "default": "medium",
                "description": (
                    "critical = revenue pipeline blocked. high = autonomous loop will break "
                    "soon. medium = wasted cycles or wrong output. low = cosmetic or future risk."
                ),
            },
            "reporter": {
                "type": "string",
                "description": "Your role_id (e.g. outreach_worker, manager, market_research_worker).",
            },
            "suggested_fix": {
                "type": "string",
                "description": "Optional. If you have a concrete idea for the fix, write it here so Scout can verify and route faster.",
            },
        },
        "required": ["title", "description", "reporter"],
    },
}
