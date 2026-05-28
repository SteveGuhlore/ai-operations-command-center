---
task_id: AUTO-20260527-160226-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-160226
---

# Scout audit: Read_inbox "interested" flag unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool's `interested: true` flag is unreliable. An email marked as interested was actually an unsubscribe request and stated the business already has a website. This can lead to incorrect CRM updates and wasted outreach efforts. The specific email was from "Literacy Council <info@plymouthcantonliteracy.org>" with the subject "Re: Winding Way Literacy — quick question".

## Suggested Fix (from reporter)
Manually verify the content of emails marked as `interested: true` before updating CRM or creating follow-up tasks.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they are unsubscribe requests or indicate the business already has a website. This leads to incorrect CRM updates and wasted outreach efforts. The specific example is an email from "Literacy Council <info@plymouthcantonliteracy.org>" with the subject "Re: Winding Way Literacy — quick question".
*   **Recommended Fix:** The `heavy_worker` needs to revise the `read_inbox` tool's logic to accurately detect disinterest, unsubscribe requests, and existing website mentions. This fix is already being tracked under task ID AUTO-20260527-151001-revise-read-inbox-tool-for-acc. A new task (AUTO-20260527-162429-confirm-read-inbox-fix-address) has been created to ensure this specific instance is covered.
