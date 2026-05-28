---
task_id: AUTO-20260527-164049-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260527-164049
---

# Scout audit: read_inbox `interested` flag is unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool frequently misidentifies unsubscribe requests or rejections as "interested: true". Manual verification of email content is crucial. The email from "Literacy Council" (Re: Winding Way Literacy — quick question) was flagged as interested:true, but the content explicitly stated "You have the wrong literacy council. We most definitely have a website. Please remove me from any further emails." Another email from "info rufflifepet.com" was also flagged incorrectly by the system as not interested when it was a clear STOP.

## Suggested Fix (from reporter)
Implement a more robust sentiment analysis or keyword matching within the `read_inbox` tool to accurately assess user intent, or remove the `interested` flag functionality and rely solely on manual review.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report is confirmed. This issue, concerning the `read_inbox` tool inaccurately flagging emails as "interested: true" despite clear indicators of disinterest or unsubscribe requests, has been repeatedly identified.

A high-priority task has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection. This task, `AUTO-20260527-151001-revise-read-inbox-tool-for-acc`, includes all the details provided in the original request, including the specific instances of the problem with the "Literacy Council" and "info rufflifepet.com" emails. Therefore, no further action is required from me at this time, as a fix is already being addressed by the `heavy_worker`.
