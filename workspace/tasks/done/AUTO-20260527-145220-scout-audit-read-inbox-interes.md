---
task_id: AUTO-20260527-145220-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-145220
---

# Scout audit: read_inbox "interested" flag is unreliable and generates false positives

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool incorrectly flagged an email as "interested: true" from "Literacy Council" (info@plymouthcantonliteracy.org) regarding "Winding Way Literacy". The email content explicitly states, "We most definitely have a website. Please remove me from any further emails." This is a recurring pattern where the tool misinterprets unsubscribe requests or general replies as interest, leading to incorrect CRM updates and potential for repeated outreach to uninterested prospects. This specific instance relates to an email sent on May 26, 2026, 2:59 AM, with the subject "Winding Way Literacy — quick question".

## Suggested Fix (from reporter)
Review and refine the `read_inbox` tool's natural language processing or keyword matching logic for identifying genuine interest. Implement additional checks to differentiate between positive replies and unsubscribe requests/clarifications. Perhaps prioritize keywords indicating removal or existing services over generic replies.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they explicitly contain unsubscribe requests or statements of disinterest (e.g., "Please remove me from any further emails."). This leads to false positives and repeated outreach to uninterested prospects.
*   **Recommended Fix:** Revise the `read_inbox` tool's natural language processing or keyword matching logic to accurately identify and exclude uninterested emails and unsubscribe requests. Implement more sophisticated checks to differentiate genuine interest from negative responses or removal requests.

A high-priority task has been created for the `heavy_worker` to revise the `read_inbox` tool's logic to accurately identify and exclude uninterested emails.

**Task ID:** AUTO-20260527-151001-revise-read-inbox-tool-for-acc
**Assigned Agent:** `heavy_worker`
**Priority:** High
