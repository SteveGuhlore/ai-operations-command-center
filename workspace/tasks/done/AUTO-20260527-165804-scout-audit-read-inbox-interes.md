---
task_id: AUTO-20260527-165804-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-165804
---

# Scout audit: `read_inbox` 'interested' flag unreliable for rejections

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool's 'interested' flag incorrectly marked an unsubscribe request as 'interested: true'. The email body clearly states 'Please remove me from any further emails.' This leads to false positives and potential misclassification of prospects.

## Suggested Fix (from reporter)
The `read_inbox` tool needs to improve its sentiment analysis or keyword detection for email bodies to accurately identify rejections/unsubscribes versus genuine interest. Manual review of email bodies for 'interested: true' flags is currently required.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection (Task ID: AUTO-20260527-151001-revise-read-inbox-tool-for-acc). Therefore, no further action is required from me at this time.
