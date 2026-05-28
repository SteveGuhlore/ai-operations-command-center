# Guardrails And Budgets

## Goal

Define the approval boundaries and budget posture needed for a generic 24/7 operations foundation.

## Guardrail themes

- No secrets in tracked files.
- No external posting without human approval.
- No spending above budget without approval.
- No destructive file operations without approval.
- No real account actions without approval.
- Moderation required for publishable content and media.

## Budget themes

- Keep a daily overall token and spend ceiling.
- Track separate per-role limits so heavier roles do not consume the whole budget.
- Cap retries per role.
- Alert before budgets are exhausted.
- Stop nonapproved work at the shutdown threshold.

## Why both matter

Guardrails control what the system is allowed to do. Budgets control how long and how expensively it can keep doing it. Both are required for safe 24/7 operation planning.

## Config sources

See:
- [guardrails.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\guardrails.example.yaml)
- [budgets.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\budgets.example.yaml)
