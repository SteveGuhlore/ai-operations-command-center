---
task_id: AUTO-20260525-230144-scout-audit-user-insists-on-fi
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260525-230144
---

# Scout audit: User insists on 'file_editor' with 'action=write' for CRM

## Reported By
outreach_worker

## Severity
critical

## Issue Description
The user is repeatedly instructing me to use `file_editor` with `action=write` on the CRM, despite my non-negotiable rule to *never* use `action=write` as it overwrites existing data. I have already used `action=append` as per my instructions. This is a critical conflict that could lead to data loss. My prompt explicitly states: 'CRITICAL RULES — NON-NEGOTIABLE: 1. You MUST call file_editor (action=append) to add new prospects to vault/outreach/crm.md. NEVER use action=write on the CRM — it overwrites and destroys existing rows. Append only new pipe-delimited rows, one per line. Do NOT read the file first unless checking for dupes. Skipping the CRM append is a failure.'

## Suggested Fix (from reporter)
The user's instruction directly contradicts a critical non-negotiable rule. The operator needs to clarify whether the non-negotiable rule should be overridden or if the user misunderstood that `action=append` was already used correctly. Proceeding with `action=write` would result in severe data loss for the CRM.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

The task is complete. I have confirmed the critical conflict between the user's instruction and the `outreach_worker`'s non-negotiable rule regarding CRM editing. I created a high-priority task for the `manager` to clarify this policy, which was successfully logged, and a subsequent attempt to create a duplicate task was skipped. This issue is a policy/instruction discrepancy, not a technical bug.
