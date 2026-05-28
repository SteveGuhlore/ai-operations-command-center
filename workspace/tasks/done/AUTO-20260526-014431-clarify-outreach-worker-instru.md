---
task_id: AUTO-20260526-014431-clarify-outreach-worker-instru
assigned_agent: manager
status: done
priority: high
pod: general
task_type: instruction_update
created_at: 20260526-014431
---

# Clarify outreach_worker instructions for contact lookup due to web_research CAPTCHA failures

The `web_research` tool consistently fails to extract contact information due to recurring CAPTCHA challenges. This directly contradicts the `outreach_worker`'s instructions to gather contact details and forces prospects to be marked as `call_queued`. A high-priority task for the `heavy_worker` to fix the `web_research` CAPTCHA issue is already pending. 

**Manager Action Required:** Please provide updated instructions for the `outreach_worker` to address this workflow blockage. Options include:
1. Temporarily instructing the `outreach_worker` to prioritize 'call_queued' status for all prospects until the `web_research` tool is fixed.
2. Providing an alternative method for contact information retrieval if available.
3. Acknowledging that the current process of gathering contact info via `web_research` is non-functional and adjust expectations accordingly.

This will prevent the `outreach_worker` from being stuck in a contradictory loop and ensure clear operational guidelines.


## Agent Output

I have logged this workflow blockage as a pattern and issued a new high-priority task to the `outreach_worker`. They will now bypass the failing `web_research` step and queue prospects directly for calls until the CAPTCHA issue is resolved. This prevents the agent from getting stuck and keeps the pipeline moving.

| Task ID | Agent | Title |
|---|---|---|
| `AUTO-20260526-014844-temporary-policy-skip-web-rese` | outreach_worker | Temporary Policy: Skip Web Research and Queue Prospects for Calls |
