---
task_id: AUTO-20260526-002731-pitch-continuous-outreach
assigned_agent: outreach_worker
status: done
priority: normal
pod: general
task_type: prospect_research
created_at: 20260526-002731
---

# Pitch: Continuous Outreach

Easy Simple Sites outreach. Find Massachusetts local businesses with NO website.

- Search 3-4 cities, 1 category each. Pick cities/categories not used recently (check memory).
- Use find_prospects only. Do NOT use web_research.
- Append new rows to vault/outreach/crm.md using file_editor action=append. NEVER use action=write.
- Row format: | Business | Type | City, MA | phone | call | call_queued | YYYY-MM-DD | notes |
- End: call create_task to queue next run, call write_memory to log cities/categories tried.


## Agent Output

Run completed via tool calls: read_inbox, file_editor, find_prospects, write_memory. Check CRM for new entries.
