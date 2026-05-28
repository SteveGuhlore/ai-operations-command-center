---
task_id: AUTO-20260525-162245-audit-crm-follow-up-task-creat
assigned_agent: debug_worker
status: failed
priority: high
pod: general
task_type: code_review
created_at: 20260525-162245
---

# Audit CRM follow-up task creation logic

An issue has been identified where follow-up tasks are being created for leads with a 'new' status, instead of 'emailed' or 'dm_sent'. This is causing conflicting instructions for the outreach_worker. Please investigate the codebase to identify the logic responsible for creating these follow-up tasks. Verify that the logic checks for the correct status ('emailed' or 'dm_sent') and that the appropriate waiting period (4 days) has passed before creating a follow-up task. Report your findings and recommend any necessary changes.
