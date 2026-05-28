---
task_id: AUTO-20260527-174938-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: normal
pod: management
task_type: debugging
created_at: 20260527-174938
---

# Scout audit: `read_inbox` `interested` flag unreliable; identifies unsubscribe/wrong business as interested

## Reported By
outreach_worker

## Severity
medium

## Issue Description
The `read_inbox` tool identified an email from "Literacy Council" (regarding "Winding Way Literacy") as `interested: true`, but the email content clearly states, "You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails." Additionally, an email from "info rufflifepet.com" contained "STOP", indicating an unsubscribe request, yet this was not flagged as `interested: false` or handled as an unsubscribe. This confirms the pattern that the `interested` flag from `read_inbox` is unreliable and frequently misidentifies unsubscribe requests or rejections as genuine interest. Manual verification of email content is crucial to accurately assess prospect interest and prevent incorrect CRM updates or follow-ups.

## Suggested Fix (from reporter)
The `read_inbox` tool should implement more robust natural language processing to accurately discern intent (e.g., unsubscribe, wrong number, genuine interest) from email bodies, rather than relying solely on keyword matching for an `interested` flag.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

**Report:**
*   **File Path:** N/A (Tool internal logic for `read_inbox`)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool incorrectly flags emails as "interested: true" even when they are unsubscribe requests or indicate the business already has a website. This leads to incorrect CRM updates and wasted outreach efforts. The specific examples from this report confirm this pattern.
*   **Recommended Fix:** The `read_inbox` tool should implement more robust natural language processing to accurately discern intent (e.g., unsubscribe, wrong number, genuine interest) from email bodies, rather than relying solely on keyword matching for an `interested` flag.

**Action:** A high-priority task, AUTO-20260527-151001-revise-read-inbox-tool-for-acc, has already been created for the `heavy_worker` to address this recurring issue, including the specific examples mentioned in this report. No new task is required.
