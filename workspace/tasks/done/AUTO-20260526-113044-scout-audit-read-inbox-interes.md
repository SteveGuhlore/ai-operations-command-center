---
task_id: AUTO-20260526-113044-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-113044
---

# Scout audit: `read_inbox` `interested: true` is unreliable

## Reported By
outreach_worker

## Severity
high

## Issue Description
`read_inbox` returned `interested: true` for 'Winding Way Literacy' but the email content clearly states they have a website and want to be removed from the mailing list. This flag is not a reliable indicator of actual interest and is causing false positives.

## Suggested Fix (from reporter)
The `read_inbox` tool should analyze the email body content to determine interest, not just rely on auto-flagging. Or, the `interested` field should be removed and `read_inbox` should return only the raw messages and let the agent decide if it's interested or not.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

This bug report is a duplicate. I have previously confirmed this issue and created a high-priority task for the `heavy_worker` to address the `read_inbox` tool's unreliable `interested: true` flagging, especially concerning unsubscribe requests, and the `find_prospects` tool's inaccuracy in detecting websites, specifically citing "Winding Way Literacy." This issue is currently being handled by the `heavy_worker`.
