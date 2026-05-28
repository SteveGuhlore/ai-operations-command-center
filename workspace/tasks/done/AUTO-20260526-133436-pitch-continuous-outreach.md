---
task_id: AUTO-20260526-133436-pitch-continuous-outreach
assigned_agent: outreach_worker
status: done
priority: normal
pod: general
task_type: prospect_research
created_at: 20260526-133436
---

# Pitch: Continuous Outreach

Easy Simple Sites outreach. Find local businesses with NO website. Search 3 cities, 1 category each. Pick cities/categories not used recently. For each no-website business: call web_research once (query: "[Name] [City] contact email OR instagram") to find email/IG handle. If email found → send_email immediately, status: email_sent. If IG found → send_instagram_dm, status: dm_queued. If nothing → status: call_queued. Append new rows to vault/outreach/crm.md using file_editor action=append. NEVER use action=write. Row format: | Business | Type | City, MA | contact | channel | status | YYYY-MM-DD | notes |. End: call write_memory to log cities/categories tried.


## Agent Output

Run completed via tool calls: read_inbox, flag_issue, find_prospects, web_research, send_email, file_editor, send_instagram_dm. Check CRM for new entries.
