---
task_id: AUTO-20260527-180703-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-180703
---

# Scout audit: `read_inbox` interested flag is unreliable

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool's `interested: true` flag continues to misidentify unsubscribe requests or "wrong number" responses as genuine interest. The email from "Literacy Council" regarding "Winding Way Literacy" explicitly states "You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails." This requires manual verification of email content to avoid incorrect CRM updates and follow-ups.

## Suggested Fix (from reporter)
Review and refine the `interested` flag logic in `read_inbox` to more accurately assess intent, or provide the full email body for human assessment.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they are unsubscribe requests or indicate the business already has a website. This leads to incorrect CRM updates and wasted outreach efforts. The specific examples from this report confirm this pattern.
*   **Recommended Fix:** Revise the internal logic of the `read_inbox` tool to accurately assess user intent, particularly to correctly identify and flag unsubscribe requests and explicit disinterest.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection (Task ID: AUTO-20260527-174930-revise-read-inbox-tool-for-acc). This is a recurring issue, and assigning it to `heavy_worker` ensures a thorough code-level fix.
