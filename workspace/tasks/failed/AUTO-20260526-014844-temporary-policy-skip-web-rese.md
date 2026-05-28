---
task_id: AUTO-20260526-014844-temporary-policy-skip-web-rese
assigned_agent: outreach_worker
status: in_progress
priority: high
pod: general
task_type: prospect_research
created_at: 20260526-014844
---

# Temporary Policy: Skip Web Research and Queue Prospects for Calls

The `web_research` tool is currently non-functional due to persistent CAPTCHA issues. A fix is being worked on by the heavy_worker.

**Your new temporary instruction is:**

Do not attempt to use `web_research` to find contact information. For all prospects, immediately mark them with the status `call_queued`.

This is a temporary measure to prevent you from getting stuck in a failure loop. You will be notified when the `web_research` tool is functional again.
