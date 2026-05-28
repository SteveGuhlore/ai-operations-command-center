---
task_id: AUTO-20260527-195403-scout-audit-read-inbox-still-m
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-195403
---

# Scout audit: read_inbox still misidentifies rejections as "interested"

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool continues to incorrectly flag unsubscribe requests or explicit rejections as "interested: true". This leads to false positives and potential for inappropriate follow-ups. Manual review of email body content is necessary to correctly interpret prospect intent. This has been flagged multiple times and remains an issue.

## Suggested Fix (from reporter)
Improve the NLP model for email intent detection in read_inbox to accurately distinguish between positive interest, rejections, and unsubscribe requests.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug is confirmed. The `read_inbox` tool continues to inaccurately flag emails as "interested: true" despite clear indicators of disinterest, rejections, or unsubscribe requests. This leads to false positives and inappropriate follow-ups, as described in the issue. This is a recurring problem, and based on previous audit tasks, a high-priority task for the `heavy_worker` already exists to revise the internal logic of the `read_inbox` tool for accurate interest flagging and unsubscribe detection. This type of complex internal tool revision is beyond the `debug_worker`'s scope.

**Report:**
*   **File Path:** N/A (Internal tool logic)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly marks emails as 'interested: true' when they contain clear rejections or unsubscribe requests. The NLP model for intent detection is not accurately distinguishing prospect intent.
*   **Recommended Fix:** Improvement of the `read_inbox` tool's internal NLP model for email intent detection to accurately differentiate between positive interest, rejections, and unsubscribe requests.

A high-priority task for the `heavy_worker` to address this issue already exists.
