---
task_id: AUTO-20260527-214247-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-214247
---

# Scout audit: `read_inbox` `interested` flag is unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool returned `interested: true` for an email that explicitly states the business already has a website and wants to be removed from the mailing list. This leads to incorrect CRM updates and task creation. Also, a 'STOP' email was incorrectly flagged as `interested: false` when it should be treated as `no_interest`.

## Suggested Fix (from reporter)
Improve the `read_inbox`'s `interested` detection logic to better parse negative responses and unsubscribe requests.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug is confirmed. The `read_inbox` tool continues to inaccurately flag emails as "interested: true" despite clear indicators of disinterest, rejections, or unsubscribe requests, and also misclassifies explicit 'STOP' messages. This leads to false positives and inappropriate follow-ups, as described in the issue. This is a recurring problem, and based on previous audit tasks, a high-priority task for the `heavy_worker` already exists to address the internal logic of the `read_inbox` tool.

**Report:**
*   **File Path:** N/A (Internal tool logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly identifies negative responses, including explicit unsubscribe requests (e.g., "already has a website and wants to be removed from the mailing list") and 'STOP' messages. It flags these as `interested: true` or misclassifies 'STOP' as `interested: false` instead of `no_interest`.
*   **Recommended Fix:** Improve the internal logic of the `read_inbox` tool to accurately detect and classify negative intent, unsubscribe requests, and 'STOP' messages.

A new task for the `heavy_worker` was not created because a similar high-priority task already exists. This recurring pattern of misclassification by the `read_inbox` tool has been logged.
