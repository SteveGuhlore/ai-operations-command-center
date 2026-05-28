---
task_id: AUTO-20260527-201058-scout-audit-read-inbox-incorre
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-201058
---

# Scout audit: `read_inbox` incorrectly flags unsubscribe as interested

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool flagged an email as `interested: true` but the email body clearly states "Please remove me from any further emails." This leads to false positives and potential for inappropriate follow-ups.

## Suggested Fix (from reporter)
Review and improve the intent detection logic within the `read_inbox` tool, possibly by incorporating negative keywords or more sophisticated NLP to accurately identify unsubscribe requests or rejections.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug is confirmed. The `read_inbox` tool continues to inaccurately flag emails as "interested: true" despite clear indicators of disinterest, rejections, or unsubscribe requests. This leads to false positives and inappropriate follow-ups, as described in the issue. This is a recurring problem, and based on previous audit tasks, a high-priority task for the `heavy_worker` already exists to address this specific issue with the `read_inbox` tool's internal logic. This type of complex internal tool revision is beyond the `debug_worker`'s scope.

**Report:**
*   **File Path:** N/A (Internal tool logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly marked an email as 'interested: true' despite the clear unsubscribe request "Please remove me from any further emails."
*   **Recommended Fix:** Revise the intent detection logic within the `read_inbox` tool to accurately identify unsubscribe requests and other negative intent, incorporating negative keywords or more sophisticated NLP.
