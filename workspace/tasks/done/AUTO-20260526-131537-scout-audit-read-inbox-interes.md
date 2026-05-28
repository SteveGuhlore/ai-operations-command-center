---
task_id: AUTO-20260526-131537-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-131537
---

# Scout audit: read_inbox "interested: true" is unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool returned an email flagged as "interested: true", but the email body explicitly stated the business has a website and requested removal from the mailing list. This indicates the "interested" flag is not a reliable indicator of actual prospect interest and can lead to wasted effort.

## Suggested Fix (from reporter)
The "interested" flag should be re-evaluated for accuracy, or a more robust text analysis of the email body is needed to confirm genuine interest.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified and is currently being addressed.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool misinterprets email content, leading to incorrect "interested: true" flags even when emails contain explicit unsubscribe requests or state that a business already has a website. This results in wasted effort for follow-up.
*   **Recommended Fix:** Revision of the `read_inbox` tool's logic to perform more robust text analysis, accurately interpret user intent (e.g., unsubscribe, existing website), and refine the "interested" flag's reliability.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection. This bug is currently being handled under a task similar to AUTO-20260526-131530-revise-read-inbox-for-accurate. No new task is needed at this time, as the fix is already in progress.
