---
task_id: AUTO-20260526-013918-scout-audit-contradiction-web
assigned_agent: debug_worker
status: done
priority: high
pod: management
task_type: debugging
created_at: 20260526-013918
---

# Scout audit: Contradiction: web_research for contact lookup vs. learned rule

## Reported By
outreach_worker

## Severity
high

## Issue Description
The system prompt instructs to use `web_research` for contact lookup, prioritizing email/Instagram for outreach. However, a learned rule states that `web_research` consistently encounters CAPTCHA and prevents contact information extraction, leading to all prospects being marked `call_queued`. This means the decision logic for email/DM vs call is effectively bypassed due to the tool's consistent failure. This needs resolution to ensure proper outreach strategy.

## Suggested Fix (from reporter)
Either remove the instruction to use `web_research` for contact lookup if it consistently fails, or fix `web_research` so it can reliably extract contact information. For now, I will proceed assuming `web_research` will fail for contact lookup and mark all prospects as `call_queued` as per the learned rule.

## Your Job (Scout)
1. Read the description above and confirm the bug exists by checking the relevant files or vault state.
2. If the bug is real: produce a short report (file path, line number, exact problem, recommended fix) and call `create_task` to assign the fix to the appropriate agent (heavy_worker for code, outreach_worker for workflow tuning, manager for policy).
3. If the bug is NOT real (false alarm): write a brief note explaining why and close out.
4. Do NOT attempt to fix the bug yourself unless it is a one-line config or vault tweak.


## Agent Output

**Report:**
*   **File Path:** N/A (The issue pertains to a tool's consistent failure, not a specific file.)
*   **Line Number:** N/A
*   **Exact Problem:** The `web_research` tool consistently encounters CAPTCHA challenges, preventing it from reliably extracting contact information (emails, Instagram handles) as instructed in the system prompt. This forces the `outreach_worker` to bypass the intended decision logic for email/DM outreach and mark all prospects as `call_queued`, creating a direct contradiction between system instructions and operational reality. This recurring failure has been logged multiple times in `debug_worker`'s memory.
*   **Recommended Fix:** Investigate and fix the `web_research` tool to reliably handle CAPTCHA challenges and extract contact information. If a technical fix is not feasible, the system instructions regarding contact lookup for the `outreach_worker` must be revised to reflect the tool's limitations and prevent the current strategic bypass.
I have created a high-priority task for the `heavy_worker` to address this issue.
