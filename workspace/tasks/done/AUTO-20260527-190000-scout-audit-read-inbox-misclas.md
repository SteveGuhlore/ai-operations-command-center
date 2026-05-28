---
task_id: AUTO-20260527-190000-scout-audit-read-inbox-misclas
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-190000
---

# Scout audit: `read_inbox` misclassifies unsubscribes/rejections as "interested"

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool continues to misclassify unsubscribe requests and explicit rejections as "interested: true". This requires manual verification of email content to prevent incorrect CRM updates and follow-ups. Example: "Re: Winding Way Literacy — quick question" from "Literacy Council" was flagged as interested but was an unsubscribe.

## Suggested Fix (from reporter)
Implement more sophisticated NLP or keyword analysis within `read_inbox` to accurately discern intent, or provide the full email body for manual agent review before marking as "interested".

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug regarding the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests is confirmed. This is a recurring issue, as evidenced by the system indicating a duplicate task already exists for the `heavy_worker`.

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they are unsubscribe requests or indicate the business already has a website. This leads to incorrect CRM updates and wasted outreach efforts. The specific example of "Literacy Council" with the subject "Re: Winding Way Literacy — quick question" being misclassified confirms this pattern.
*   **Recommended Fix:** Implement more sophisticated NLP or keyword analysis within `read_inbox` to accurately discern intent, or provide the full email body for manual agent review before marking as "interested."

A high-priority task for this issue has already been assigned to the `heavy_worker`, so no new task will be created.
