# Home Handoff

## Goal at home

Review the command center foundation locally, replace the sample profile with a real project profile when ready, and confirm the dry-run flow behaves as expected.

## First commands

From the command center folder:

```powershell
.\scripts\doctor.ps1
.\scripts\validate-project.ps1 -ProjectProfile projects\sample-project.yaml -AllowPlaceholderPath
.\scripts\validate-tasks.ps1
.\scripts\new-batch.ps1 -BatchId BATCH-001 -Project sample-project
.\scripts\safe-launch.ps1 -HeavyWorkers 1 -DebugWorkers 1 -DryRun
```

Dry-run processes up to one task per worker per launch, writes run logs, and creates a batch report in `workspace/reports`.

## Do not do yet

- Do not run real workers until dry-run behavior is reviewed.
- Do not point the sample profile at a real project until you are ready.
- Do not connect API keys or secrets until the command-center scripts are proven safe.
