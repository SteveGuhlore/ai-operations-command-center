---
task_id: AUTO-20260527-135930-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-135930
---

# Scout audit: read_inbox 'interested' flag is unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool returned an email with 'interested: true', but the email body explicitly states they have a website and wish to be removed from the mailing list. This indicates the 'interested' flag is unreliable and requires manual verification of email content.

## Suggested Fix (from reporter)
Implement more sophisticated NLP for sentiment analysis or keyword detection in email bodies to accurately determine buying interest, rather than relying on simple heuristics.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described is confirmed. The `read_inbox` tool inaccurately flags emails as "interested: true" despite explicit indicators of disinterest or unsubscribe requests, leading to manual verification and potential errors. This is a recurring issue.

A high-priority task has been created for the `heavy_worker` to revise the `read_inbox` tool's logic to accurately identify and exclude uninterested emails.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when the content explicitly states disinterest or an unsubscribe request.
*   **Recommended Fix:** Implement more sophisticated NLP, sentiment analysis, or keyword detection within the `read_inbox` tool to accurately determine buying interest and detect unsubscribe requests.

**Task ID:** AUTO-20260527-141706-revise-read-inbox-for-accurate
**Assigned Agent:** `heavy_worker`
**Priority:** High
