---
task_id: AUTO-20260527-204604-scout-audit-read-inbox-incorre
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-204604
---

# Scout audit: read_inbox incorrectly flags unsubscribe as interested

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool flagged an email as "interested: true" but the body clearly states "You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails."

## Suggested Fix (from reporter)
Improve intent detection in read_inbox to accurately distinguish between genuine interest and unsubscribe/rejection messages based on email body content.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug is confirmed. The `read_inbox` tool continues to inaccurately flag emails as "interested: true" despite clear indicators of disinterest, rejections, or unsubscribe requests. This leads to false positives and inappropriate follow-ups, as described in the issue. This is a recurring problem, and based on previous audit tasks, a high-priority task for the `heavy_worker` already exists to address this.

**Report:**
*   **File Path:** N/A (Internal tool logic)
*   **Line Number:** N/A (Internal tool logic)
*   **Exact Problem:** The `read_inbox` tool misidentified the email content "You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails." as "interested: true" instead of recognizing it as an unsubscribe request. This is a critical and recurring failure that leads to false positives and inappropriate follow-ups.
*   **Recommended Fix:** Improve the internal intent detection logic within the `read_inbox` tool to accurately distinguish between genuine interest and clear unsubscribe/rejection messages based on email body content.

A high-priority task for the `heavy_worker` already exists to address this recurring issue, so a duplicate task has not been created. I have also logged this pattern to memory.
