---
task_id: AUTO-20260525-172129-scout-audit-web-research-tool
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260525-172129
---

# Scout audit: Web Research Tool Out of Credits

## Reported By
outreach_worker

## Severity
critical

## Issue Description
The `web_research` tool returned a RESOURCE_EXHAUSTED error. This prevents the agent from verifying websites and extracting contact information for prospects, effectively blocking the outreach workflow.

## Suggested Fix (from reporter)
Replenish prepayment credits for the `web_research` tool.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The task is complete. I have confirmed the issue, reported it, and created a task for the manager to address. I have also logged this outcome in my memory.
