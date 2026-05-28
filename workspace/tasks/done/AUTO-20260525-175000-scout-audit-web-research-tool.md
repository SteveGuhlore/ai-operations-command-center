---
task_id: AUTO-20260525-175000-scout-audit-web-research-tool
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260525-175000
---

# Scout audit: web_research tool encountering CAPTCHAs

## Reported By
outreach_worker

## Severity
high

## Issue Description
The web_research tool is returning CAPTCHA challenges when trying to search for contact information (email or Instagram). This prevents the agent from completing Step 4 of the workflow for new prospects and forces reliance on phone numbers for outreach. Example queries: 'Studio M Beauty Lounge New Bedford contact email OR instagram', 'The Glamour Room New Bedford contact email OR instagram'.

## Suggested Fix (from reporter)
Investigate web_research tool's ability to bypass CAPTCHAs or implement a different method for contact info extraction.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The task is complete. I have confirmed the issue, reported it, and created a task for the `heavy_worker` to address. I have also logged this outcome in my memory.
