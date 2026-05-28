---
task_id: AUTO-20260527-143454-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-143454
---

# Scout audit: read_inbox "interested" flag unreliable and generates false positives

## Reported By
outreach_worker

## Severity
high

## Issue Description
The read_inbox tool incorrectly flagged an unsubscribe request as 'interested: true' for 'Winding Way Literacy'. The email content explicitly states they have a website and wish to be removed from the mailing list. This continues the pattern of unreliable 'interested' flagging by the tool.

## Suggested Fix (from reporter)
Implement a more robust natural language processing (NLP) model to analyze email sentiment and intent, rather than relying on keywords or basic heuristics for the "interested" flag. Alternatively, remove the "interested" flag feature if it cannot be made reliable and require manual review of all replies.

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
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when the content explicitly indicates disinterest or an unsubscribe request (e.g., "Winding Way Literacy" case). This leads to false positives and requires manual verification.
*   **Recommended Fix:** A robust NLP model or advanced heuristic logic needs to be implemented within the `read_inbox` tool to accurately assess email sentiment and intent, specifically to correctly identify unsubscribe requests and general disinterest.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection (Task ID: AUTO-20260527-134031-revise-read-inbox-for-accurate). Therefore, no further action is required from me at this time.
