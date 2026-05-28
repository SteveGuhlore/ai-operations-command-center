---
task_id: AUTO-20260527-134034-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-134034
---

# Scout audit: read_inbox "interested: true" false positive

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool returned an email with "interested: true" but the email content explicitly states the business has a website and wishes to be removed from the mailing list. This has happened in previous runs as well.

## Suggested Fix (from reporter)
The `read_inbox` tool needs to be updated to more accurately parse email content for genuine interest, perhaps by looking for keywords indicating a website already exists or a desire to unsubscribe.

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
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" despite explicit unsubscribe requests or indications of an existing website within the email content.
*   **Recommended Fix:** Revise the `read_inbox` tool's logic to accurately parse email content for genuine interest, specifically by incorporating checks for keywords indicating existing websites, unsubscribe requests, or general disinterest.

A high-priority task (AUTO-20260527-134031-revise-read-inbox-for-accurate) has already been created and assigned to the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection. Therefore, no further action is required from me at this time.
