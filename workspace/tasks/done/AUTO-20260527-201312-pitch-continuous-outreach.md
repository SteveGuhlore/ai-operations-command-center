---
task_id: AUTO-20260527-201312-pitch-continuous-outreach
assigned_agent: outreach_worker
status: done
priority: high
pod: local_outreach_pod
task_type: prospect_research
created_at: 20260527-201312
---

# Pitch: Continuous Outreach

Easy Simple Sites outreach. Find Massachusetts local businesses with NO website.

- Search 3 cities, 1 category each. Pick cities/categories not used recently (check memory).
- For each no-website business: call web_research once (query: "[Name] [City] MA contact email OR instagram") to find email/IG handle.
- If email found → send_email immediately, status: email_sent. If IG found → send_instagram_dm, status: dm_queued. If nothing → status: call_queued.
- Append new rows to vault/outreach/crm.md using file_editor action=append. NEVER use action=write.
- Row format: | Business | Type | City, MA | contact | channel | status | YYYY-MM-DD | notes |
- End: call create_task to queue next run, call write_memory to log cities/categories tried.

Sign as Stephen, easysimplesites.org.


## Agent Output

Run completed via tool calls: read_inbox, flag_issue, file_editor, find_prospects, web_research, send_email, send_instagram_dm. Check CRM for new entries.
