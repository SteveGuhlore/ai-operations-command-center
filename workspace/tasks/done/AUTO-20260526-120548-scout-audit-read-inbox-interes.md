---
task_id: AUTO-20260526-120548-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-120548
---

# Scout audit: `read_inbox` "interested" flag is unreliable and `find_prospects` identifies businesses with websites as having none

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool incorrectly flags emails as "interested: true" even when the content is a request to be removed from the mailing list because the business already has a website. This also implies that `find_prospects` is incorrectly identifying businesses that have websites as having no website. Example: Email from "Literacy Council" regarding "Winding Way Literacy".

## Suggested Fix (from reporter)
Review and refine the logic for identifying "interested" emails in `read_inbox` and improve `find_prospects` accuracy in determining if a business has a website.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report has already been confirmed and addressed in previous audits. I have created a high-priority task for the `heavy_worker` to address the `read_inbox` tool's unreliable `interested: true` flagging, especially concerning unsubscribe requests, and the `find_prospects` tool's inaccuracy in detecting websites, specifically citing "Winding Way Literacy." This issue is currently being handled by the `heavy_worker`.
