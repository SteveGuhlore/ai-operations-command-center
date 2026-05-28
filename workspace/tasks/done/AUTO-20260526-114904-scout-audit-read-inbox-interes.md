---
task_id: AUTO-20260526-114904-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-114904
---

# Scout audit: `read_inbox` "interested" flag is unreliable and `find_prospects` identifies businesses with websites as having none

## Reported By
outreach_worker

## Severity
high

## Issue Description
Received an email from "Literacy Council" (Winding Way Literacy) flagged as "interested: true" but the email content clearly states they have a website and wish to be removed from the mailing list. This indicates `read_inbox`'s "interested" flag is unreliable and `find_prospects` is incorrectly identifying businesses with websites as having none.

## Suggested Fix (from reporter)
Improve the accuracy of `find_prospects` in identifying businesses without websites and refine the `read_inbox`'s "interested" flag logic to be more accurate.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report has already been confirmed and addressed in previous audits.

**Report:**
*   **File Path:** N/A (Tool internal logic for both `read_inbox` and `find_prospects`)
*   **Line Number:** N/A
*   **Exact Problem:**
    *   The `find_prospects` tool incorrectly identified "Winding Way Literacy" as lacking a website.
    *   The `read_inbox` tool misclassified an unsubscribe request from "Literacy Council" (Winding Way Literacy) as "interested: true".
*   **Recommended Fix:** Refine the internal logic of the `find_prospects` tool for accurate website detection and improve the sentiment analysis and "interested" flag logic within the `read_inbox` tool.

This issue is a duplicate and has been previously escalated. A high-priority task for the `heavy_worker` to address these inaccuracies has already been created. This issue is currently being handled by the `heavy_worker`.
