---
task_id: AUTO-20260527-182321-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-182321
---

# Scout audit: read_inbox "interested" flag is inaccurate

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool's "interested: true" flag is unreliable, frequently misidentifying unsubscribe requests as genuine interest or outright rejections. For example, "Winding Way Literacy" was flagged as interested but explicitly stated they have a website and want to be removed from the mailing list. Manual verification of email content is crucial to accurately assess prospect interest and prevent incorrect CRM updates or follow-ups.

## Suggested Fix (from reporter)
The `interested` flag should be removed or improved to accurately reflect interest. Manual review of email body is required for now.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug concerning the `read_inbox` tool's inaccurate "interested: true" flag has been confirmed. This issue, exemplified by the "Winding Way Literacy" case where an unsubscribe request was misidentified as interest, is a recurring problem leading to incorrect CRM updates and wasted outreach efforts.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they contain explicit unsubscribe requests or state that the business already has a website.
*   **Recommended Fix:** The internal logic of the `read_inbox` tool requires revision to accurately interpret email content for genuine interest, explicitly recognize unsubscribe requests, and not misinterpret mentions of existing websites as indicators of interest.

A high-priority task (AUTO-20260527-184034-revise-read-inbox-tool-for-acc) has been created and assigned to the `heavy_worker` to address this issue.

A memory entry has been recorded to document this recurring pattern.
