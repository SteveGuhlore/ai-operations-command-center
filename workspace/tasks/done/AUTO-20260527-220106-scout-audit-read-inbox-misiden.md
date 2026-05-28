---
task_id: AUTO-20260527-220106-scout-audit-read-inbox-misiden
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-220106
---

# Scout audit: read_inbox misidentifies intent and misses STOP

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` function incorrectly flagged an unsubscribe request as "interested: true" and failed to flag a "STOP" email as negative intent. This leads to inaccurate CRM status updates and potential re-contact of uninterested prospects. The email from "Literacy Council <info@plymouthcantonliteracy.org>" with subject "Re: Winding Way Literacy — quick question" was flagged as `interested: true` but explicitly states "We most definitely have a website. Please remove me from any further emails." The email from "info rufflifepet.com <info@rufflifepet.com>" with subject "Re: Life is Ruff — quick question" contained "STOP" but `interested` was `false` rather than `no_interest`.

## Suggested Fix (from reporter)
Review and update the `read_inbox` intent detection logic to accurately interpret negative signals like "STOP" and unsubscribe requests, and to better discern actual interest from complaints or existing websites.

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
*   **Exact Problem:** The `read_inbox` tool incorrectly identifies negative responses, including explicit unsubscribe requests (e.g., "Please remove me from any further emails.") and "STOP" messages. This results in false positives for `interested: true` (when it should be `no_interest` or similar) and incorrect `interested: false` instead of `no_interest` for clear `STOP` messages.
*   **Recommended Fix:** Update the `read_inbox` intent detection logic to accurately interpret negative signals such as "STOP" messages and explicit unsubscribe requests, and to better differentiate genuine interest from complaints or acknowledgments of existing resources (like websites).

A new task to address this was skipped because a similar high-priority task for the `heavy_worker` already exists. I have recorded this recurring pattern.
