# Handoff

## What exists now

This repository is a generic AI Operations Command Center foundation with:

- file-based task workflow
- lock management
- run logs
- batch reports
- dry-run worker simulation
- validation scripts for tasks, agent config, tool config, guardrails, budgets, and revenue pods
- agent registry
- tool registry
- guardrails
- budgets
- schedules
- revenue pods
- visual UI and Star Office UI bridge plan
- shortcuts
- playbooks
- memory structure
- evaluation structure
- tool mastery structure
- config-only planning layers for model mapping, dashboard integration, 24/7 operations, and revenue pods

## What validations pass

At handoff, these commands pass:

```powershell
.\scripts\doctor.ps1
.\scripts\validate-agents.ps1
.\scripts\validate-tools.ps1
.\scripts\validate-guardrails.ps1
.\scripts\validate-budgets.ps1
.\scripts\validate-revenue-pods.ps1
.\scripts\validate-tasks.ps1
```

## What scripts exist

- `doctor.ps1`
- `validate-project.ps1`
- `validate-tasks.ps1`
- `validate-agents.ps1`
- `validate-tools.ps1`
- `validate-guardrails.ps1`
- `validate-budgets.ps1`
- `validate-revenue-pods.ps1`
- `safe-launch.ps1`
- `launch-batch.ps1`
- `auto-agent.ps1`
- `pick-task.ps1`
- `move-task.ps1`
- `release-lock.ps1`
- `clean-expired-locks.ps1`
- `status.ps1`
- `review-batch.ps1`
- `new-batch.ps1`
- `reset-sample-tasks.ps1`
- `dashboard-push.ps1` stub
- `dashboard-export-state.ps1`

## Current dry-run behavior

- `safe-launch.ps1 -HeavyWorkers 1 -DebugWorkers 1 -DryRun` runs preflight validation first.
- Dry-run does not connect APIs or start real worker integrations.
- Dry-run simulates task pickup, lock creation, task movement, run logging, lock release, and batch reporting.
- Each dry-run launch processes up to one task per worker.
- Repeated dry-runs may be needed to move all sample tasks from `todo` to `review`.
- `reset-sample-tasks.ps1` can move `SAMPLE-*` tasks back to `todo` for repeatable testing.

## Known limitations

- The system is still file- and script-driven, not service-driven.
- `validate-project.ps1` supports placeholder mode for the sample profile but no real project connection is configured.
- The dashboard layer is documentation and a stub only.
- Revenue pods are validated as config, but they are not wired into execution.
- The schedule layer exists only as planning data, not as a live daemon.

## What is still stubbed

- Real model provider adapters
- Real worker execution
- Real APIs
- Real project profile connection
- Star Office UI runtime or install
- Dashboard bridge transport
- Scheduler or daemon runtime
- 24/7 runtime
- Real revenue tracking
- External publishing, purchases, or account actions
- Any API-backed model routing

## Exact first steps at home

```powershell
cd <your-command-center-folder>
.\scripts\doctor.ps1
.\scripts\validate-project.ps1 -ProjectProfile projects\sample-project.yaml -AllowPlaceholderPath
.\scripts\validate-agents.ps1
.\scripts\validate-tools.ps1
.\scripts\validate-guardrails.ps1
.\scripts\validate-budgets.ps1
.\scripts\validate-revenue-pods.ps1
.\scripts\validate-tasks.ps1
```

After validations pass:

1. install Node.js and npm if needed
2. install Star Office UI in its own folder
3. use the local dashboard shortcuts to test the dashboard launch path
4. test the dashboard bridge and exported state locally
5. connect the first real project profile only after validations still pass

Optional repeatable dry-run check:

```powershell
.\scripts\reset-sample-tasks.ps1
.\scripts\safe-launch.ps1 -HeavyWorkers 1 -DebugWorkers 1 -DryRun
```

## Stop conditions

- Stop if `doctor.ps1` fails.
- Stop if any validation script fails.
- Stop if locks remain after dry-run.
- Stop if tasks remain stuck in `in_progress`.
- Stop if any step requires credentials, external posting, spending, or real worker launch.
- Stop if any API key would be written to files.
- Stop if real workers are requested before adapter review.
- Stop if any external account action is requested.
- Stop if any autonomous trading behavior is requested.

## Recommended next build phase

Recommended next build phase: `project profile connection`

Suggested order after that:
1. project profile connection
2. real model provider adapter
3. dashboard bridge
4. scheduler/daemon
5. revenue pod activation
