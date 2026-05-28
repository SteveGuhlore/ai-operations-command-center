---
task_id: AUTO-20260526-140651-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-140651
---

# Scout audit: `read_inbox` `interested: true` flag is inaccurate

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool incorrectly flagged an email as `interested: true` from 'Literacy Council'. The email body explicitly states 'You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails.' This confirms the previously identified pattern that the `interested` flag is unreliable and requires manual verification against the email body.

## Suggested Fix (from reporter)
Improve the `read_inbox` tool's sentiment analysis or pattern matching for the `interested` flag to accurately identify genuine interest, perhaps by incorporating negative keywords like 'remove me', 'wrong', 'already have a website'.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. The `read_inbox` tool is inaccurately flagging emails as "interested: true" despite explicit unsubscribe requests or indications of disinterest.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" despite explicit negative intent (e.g., "remove me", "wrong literacy council"). This indicates a failure in sentiment analysis or keyword detection for disinterest.
*   **Recommended Fix:** Enhance the `read_inbox` tool's logic to accurately identify and interpret negative keywords and phrases indicating disinterest or unsubscribe requests. This may involve improving sentiment analysis or incorporating a more robust pattern matching system for common opt-out language.

I have created a high-priority task for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection.

**Task ID:** AUTO-20260526-142316-revise-read-inbox-for-accurate
**Assigned Agent:** `heavy_worker`
**Priority:** High
**Description:** The `read_inbox` tool is inaccurately flagging emails as "interested: true" despite explicit unsubscribe requests or indications of disinterest. An example includes an email from 'Literacy Council' explicitly stating 'You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails.' but still being flagged as interested.

The `heavy_worker` needs to:
1.  Investigate the `read_inbox` tool's internal logic for interest flagging.
2.  Implement improvements to accurately identify and interpret negative keywords and phrases (e.g., "remove me", "wrong", "do not contact", "unsubscribe").
3.  Enhance sentiment analysis or pattern matching to prevent false positives for the `interested` flag.
4.  Ensure that emails with clear indicators of disinterest or unsubscribe requests are correctly flagged as `interested: false`.
