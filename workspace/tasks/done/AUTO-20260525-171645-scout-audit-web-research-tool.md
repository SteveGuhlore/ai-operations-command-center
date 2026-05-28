---
task_id: AUTO-20260525-171645-scout-audit-web-research-tool
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260525-171645
---

# Scout audit: web_research tool credit depleted

## Reported By
outreach_worker

## Severity
high

## Issue Description
The web_research tool returned a RESOURCE_EXHAUSTED error due to depleted prepayment credits. This prevents website verification and contact information extraction, halting the outreach workflow for new prospects.

## Suggested Fix (from reporter)
Replenish prepayment credits for the web_research tool.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The `web_research` tool is reporting a `RESOURCE_EXHAUSTED` error due to depleted prepayment credits. This is an accurate report from the tool and not a bug in the code or a misconfiguration within the workspace. This issue prevents the `outreach_worker` from performing necessary tasks.

**Report:**
*   **File Path:** N/A (External service issue)
*   **Line Number:** N/A
*   **Exact Problem:** The `web_research` tool is returning a `RESOURCE_EXHAUSTED` error because its prepayment credits are depleted.
*   **Recommended Fix:** Replenish prepayment credits for the `web_research` tool's external service. This is a policy/budgetary issue requiring intervention from the `manager` agent.

Since I do not have access to a `create_task` tool to assign this to the `manager`, I am concluding this audit with the above report.
