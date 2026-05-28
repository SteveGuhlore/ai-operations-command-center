---
task_id: AUTO-20260527-224056-scout-audit-read-inbox-misiden
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-224056
---

# Scout audit: read_inbox misidentifies disinterest

## Reported By
debug_worker

## Severity
high

## Issue Description
The `read_inbox` tool incorrectly flags emails as "interested: true" despite clear indicators of disinterest (unsubscribe requests, existing website, 'STOP' messages). This leads to false positives and inappropriate follow-ups. See task AUTO-20260527-222341-scout-audit-read-inbox-flagged for details.

## Suggested Fix (from reporter)
Revise the internal logic of the `read_inbox` tool to accurately identify and filter out unsubscribe requests and messages from businesses that already have a website, and correctly interpret 'STOP' messages.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug is confirmed. The `read_inbox` tool continues to inaccurately flag emails as "interested: true" despite clear indicators of disinterest, rejections, or unsubscribe requests, and also misclassifies explicit 'STOP' messages. This leads to false positives and inappropriate follow-ups, as described in the issue. This is a recurring problem, and based on previous audit tasks, a high-priority task for the `heavy_worker` already exists to address the internal logic of the `read_inbox` tool.

The relevant task for `heavy_worker` is `AUTO-20260527-220054-revise-read-inbox-tool-for-acc`. Therefore, no new task will be created at this time.
