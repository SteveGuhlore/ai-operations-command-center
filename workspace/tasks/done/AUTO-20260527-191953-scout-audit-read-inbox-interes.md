---
task_id: AUTO-20260527-191953-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-191953
---

# Scout audit: Read_inbox "interested" flag unreliable

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool incorrectly flags unsubscribe requests and rejections as "interested: true". This leads to false positives and potential for inappropriate follow-ups. Manual review of email body content is necessary to correctly interpret prospect intent. This happened again with "Literacy Council" for "Winding Way Literacy" and "info rufflifepet.com".

## Suggested Fix (from reporter)
Implement more sophisticated NLP or keyword matching in `read_inbox` to accurately discern positive intent versus unsubscribe/rejection. Prioritize keywords like "remove", "stop", "unsubscribe" over generic "interested" triggers.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug concerning the `read_inbox` tool's inaccurate "interested: true" flag has been confirmed. This issue, exemplified by the "Literacy Council" and "info@rufflifepet.com" cases where unsubscribe requests were misidentified as interest, is a recurring problem leading to incorrect CRM updates and wasted outreach efforts.

A high-priority task has already been created for the `heavy_worker` to address this issue, and it was noted that a pending debugging task already exists, so no new task was generated. I have also logged this as a recurring pattern in my memory.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags unsubscribe requests and rejections as "interested: true", leading to false positives and potential for inappropriate follow-ups. This specifically occurred with "Literacy Council" for "Winding Way Literacy" and "info@rufflifepet.com", where unsubscribe intent was misinterpreted as interest.
*   **Recommended Fix:** Implement more sophisticated NLP or keyword matching in `read_inbox` to accurately discern positive intent versus unsubscribe/rejection. Prioritize keywords like "remove", "stop", "unsubscribe" over generic "interested" triggers.
