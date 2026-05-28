---
task_id: AUTO-20260525-230644-scout-audit-imap-not-configure
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260525-230644
---

# Scout audit: IMAP not configured for inbox reading

## Reported By
outreach_worker

## Severity
high

## Issue Description
The `read_inbox` tool consistently returns an empty response with the message "IMAP is not configured." This prevents the agent from checking for replies from prospects.

## Suggested Fix (from reporter)
Configure IMAP settings for the outreach inbox.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

Report:
*   **File Path:** N/A (IMAP configuration is typically a system-level or tool-level setting, not a file within the workspace vault)
*   **Line Number:** N/A
*   **Exact Problem:** The `read_inbox` tool consistently returns "IMAP is not configured," preventing the `outreach_worker` from checking for prospect replies. This indicates a missing or incorrect IMAP setup.
*   **Recommended Fix:** Configure IMAP settings for the outreach inbox. This is an infrastructure setup task.

The bug is real. I have created a high-priority task for the `heavy_worker` to configure IMAP for the outreach inbox.
