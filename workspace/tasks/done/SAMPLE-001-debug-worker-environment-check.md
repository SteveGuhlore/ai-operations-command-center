---
task_id: SAMPLE-001
project: sample-project
assigned_agent: debug_worker
status: done
priority: high
allowed_files:
  - START_HERE.md
  - workspace/reports/**
  - workspace/runs/**
forbidden_files:
  - .env
  - "**/.env"
  - scripts/**
---

# Sample Environment Check

## Goal

Confirm the command center foundation can be validated without touching any external project.

## Context

This task is a sample that documents whether the local validation commands are available.
The assigned role is `debug_worker`, which uses the display name `Scout`.

## Files to inspect

- START_HERE.md
- scripts/doctor.ps1
- scripts/validate-project.ps1
- scripts/validate-tasks.ps1

## Files allowed to change

- START_HERE.md
- workspace/reports/**
- workspace/runs/**

## Files forbidden to change

- .env
- **/.env
- scripts/**

## Acceptance criteria

- Record which validation commands should be run.
- Note any missing folders or task metadata problems.
- Do not inspect paths outside this command center.

## Tests/checks required

- .\scripts\doctor.ps1
- .\scripts\validate-project.ps1 -ProjectProfile projects\sample-project.yaml -AllowPlaceholderPath
- .\scripts\validate-tasks.ps1

## Stop conditions

- Stop if validation would require editing files outside the command center.
- Stop if a command would launch background workers.

## Worker output required

- Summary
- Commands run
- Results
- Risks/notes


## Agent Output

---

## REPORT: SAMPLE-001 Environment Check

### Summary

The validation task cannot proceed. The required PowerShell validation scripts (`scripts/doctor.ps1`, `scripts/validate-project.ps1`, `scripts/validate-tasks.ps1`) and `START_HERE.md` documentation file do not exist in this environment.

### Files Inspection Results

| File | Status | Finding |
|------|--------|---------|
| START_HERE.md | ❌ Missing | Not found in root directory |
| scripts/doctor.ps1 | ❌ Missing | Scripts folder/files not present |
| scripts/validate-project.ps1 | ❌ Missing | Scripts folder/files not present |
| scripts/validate-tasks.ps1 | ❌ Missing | Scripts folder/files not present |

### Environment Structure Found

**Available directories:**
- assets, context, dashboard, ledger, listings, locks, logs, outputs, products, reports, runs, social, tasks

**Available task subdirectories:**
- done, failed, in_progress, review, todo

### Tests/Checks Required (Status)

- ❌ `.\scripts\doctor.ps1` — **Cannot run: script does not exist**
- ❌ `.\scripts\validate-project.ps1 -ProjectProfile projects\sample-project.yaml -AllowPlaceholderPath` — **Cannot run: script does not exist**
- ❌ `.\scripts\validate-tasks.ps1` — **Cannot run: script does not exist**

### Risks/Notes

1. **Setup incomplete**: This environment appears to be a task/project management workspace, not the command center with validation scripts described in SAMPLE-001.
2. **No stop condition triggered**: While the validation scripts are missing, no forbidden file modifications were attempted.
3. **Action blocked**: Cannot proceed with validation until the required scripts and documentation are available.

### Recommendation

SAMPLE-001 requires the command center foundation scripts and documentation to be present. This environment does not contain them. Setup of the validation framework is needed before this task can be completed.
