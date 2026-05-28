# START HERE

## What this command center is

This repository is a reusable local foundation for coordinating AI-assisted work with a manager, task files, lock files, status folders, logs, and batch reports.

## Stable display names

- `manager` uses the display name `Atlas`
- `heavy_worker` uses the display name `Forge`
- `debug_worker` uses the display name `Scout`

Keep the generic role IDs in task frontmatter and scripts. The display names are friendly labels only.

The stable role IDs are what task files, validation rules, and future config should key on. Display names help logs, reports, and handoffs stay readable.

## Run doctor

```powershell
.\scripts\doctor.ps1
```

## Validate the sample project profile

```powershell
.\scripts\validate-project.ps1 -ProjectProfile projects\sample-project.yaml -AllowPlaceholderPath
```

## Validate the sample tasks

```powershell
.\scripts\validate-tasks.ps1
```

By default, this validates tasks across all status folders: `todo`, `in_progress`, `review`, `done`, and `failed`.

## Validate the 24/7 config layer

```powershell
.\scripts\validate-agents.ps1
.\scripts\validate-tools.ps1
.\scripts\validate-guardrails.ps1
.\scripts\validate-budgets.ps1
.\scripts\validate-revenue-pods.ps1
```

## Reset sample tasks

```powershell
.\scripts\reset-sample-tasks.ps1
```

This moves only `SAMPLE-*` tasks from `review`, `done`, `failed`, or `in_progress` back to `todo` so you can repeat dry-run testing safely.

## Run dry-run only

```powershell
.\scripts\safe-launch.ps1 -HeavyWorkers 1 -DebugWorkers 1 -DryRun
```

Dry-run simulates task locking and status movement without starting background jobs or calling external APIs.
Each dry-run launch processes up to one task per worker, so repeated dry-runs may be needed to move all sample tasks from `todo` to `review`.

To repeat dry-runs safely:

```powershell
.\scripts\reset-sample-tasks.ps1
.\scripts\validate-tasks.ps1
.\scripts\safe-launch.ps1 -HeavyWorkers 1 -DebugWorkers 1 -DryRun
```

## What is still stubbed

- Real worker execution is not connected.
- Real project integration is not configured.
- Review decisions still require a human manager.
- Background worker launch exists only behind explicit `-AllowRealRun`.
- Real worker integration remains blocked unless `-AllowRealRun` is explicitly supplied.

## Future model mapping

Each role can later be mapped in configuration to MiniMax, Kimi, a Haiku-level model, Codex, or another model. No provider mapping is hard-coded in this foundation yet.

- `manager` stays the coordinating reviewer role and uses the display name `Atlas`.
- `heavy_worker` stays the implementation role and `Forge` can later use Kimi or another stronger coding model.
- `debug_worker` stays the debugging/docs role and `Scout` can later be tested between MiniMax and Haiku-level models.

See [agent-models.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\agent-models.example.yaml) for the config-only example mapping layer.

## Memory structure

Phase B memory folders now exist under [memory](C:\Users\sbattaglia\Downloads\AI Operations Command Center\memory) for successful outputs, failed outputs, retry history, pod performance, context bundles, shared knowledge, and model evaluations.

This is structured operational history only. Runtime retrieval is not built yet.

## Evaluation structure

Phase C evaluation folders now exist under [evaluations](C:\Users\sbattaglia\Downloads\AI Operations Command Center\evaluations) for rubrics, reviews, model comparisons, task scores, pod scores, failure patterns, and retry effectiveness.

This is structured operational evaluation only. Runtime scoring and automated evaluation loops are not built yet.
