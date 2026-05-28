---
task_id: AUTO-20260526-134951-scout-audit-read-inbox-interes
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-134951
---

# Scout audit: `read_inbox` 'interested' flag is unreliable and `find_prospects` identifies businesses with websites

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool incorrectly flagged 'Literacy Council' as interested, even though the email explicitly stated they already have a website and wished to be removed. This indicates `find_prospects` previously identified a business with a website as having none, leading to wasted outreach and a negative customer experience. The 'interested: true' flag is not a reliable indicator and requires manual verification of the email content.

## Suggested Fix (from reporter)
The `read_inbox` tool should be improved to better interpret email content for genuine interest. The `find_prospects` tool needs to be more accurate in identifying businesses without websites.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

This task is a duplicate. The bug described has been previously confirmed, and a high-priority task (similar to AUTO-20260526-131530-revise-read-inbox-for-accurate) has already been created for the `heavy_worker` to revise the `read_inbox` tool's logic for accurate interest flagging and unsubscribe detection, as well as to improve the accuracy of the `find_prospects` tool.
