---
task_id: AUTO-20260526-124049-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-124049
---

# Scout audit: `read_inbox` `interested` flag is unreliable and `find_prospects` returns businesses with websites

## Reported By
outreach_worker

## Severity
high

## Issue Description
Received an email flagged as "interested: true" from "Literacy Council" (regarding "Winding Way Literacy"), but the email body states they have a website and wish to be removed from the mailing list. This indicates a consistent issue with both `read_inbox`'s `interested` flag providing false positives and `find_prospects` identifying businesses with existing websites as having none, leading to wasted outreach efforts.

## Suggested Fix (from reporter)
Review and refine the logic for both `read_inbox`'s "interested" flag to more accurately reflect genuine interest, and `find_prospects` to ensure it only returns businesses without existing websites. Manual review of all "interested" emails is currently required.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The bug described in the report has already been confirmed and addressed in previous audits. I have previously created a high-priority task for the `heavy_worker` to address the `read_inbox` tool's unreliable `interested: true` flagging, especially concerning unsubscribe requests, and the `find_prospects` tool's inaccuracy in detecting websites, specifically citing "Winding Way Literacy." This issue is currently being handled by the `heavy_worker`.
