---
task_id: AUTO-20260527-171429-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-171429
---

# Scout audit: read_inbox "interested" flag is inaccurate

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool incorrectly flags emails as "interested" when the content clearly indicates a lack of interest or an unsubscribe request. For example, "Winding Way Literacy" was flagged as interested despite explicitly stating "We most definitely have a website. Please remove me from any further emails." This leads to incorrect CRM updates and wasted follow-up efforts. "Life is Ruff" also sent a "STOP" email which was not flagged as interested:false.

## Suggested Fix (from reporter)
The "interested" flag logic in read_inbox needs to be improved to accurately interpret email content for genuine interest, negative replies, or unsubscribe requests. It should use more sophisticated NLP to avoid misclassifying explicit rejections or "STOP" messages as positive interest.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection, including the specific examples mentioned in this report.

Report:
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they are unsubscribe requests or indicate the business already has a website. This leads to incorrect CRM updates and wasted outreach efforts. Specific examples include "Winding Way Literacy" and "Life is Ruff".
*   **Recommended Fix:** The "interested" flag logic in `read_inbox` needs to be improved to accurately interpret email content for genuine interest, negative replies, or unsubscribe requests, utilizing more sophisticated NLP to avoid misclassifying explicit rejections or "STOP" messages as positive interest.

This issue is being addressed by task `AUTO-20260527-151001-revise-read-inbox-tool-for-acc`, assigned to `heavy_worker`.
