# Star Office UI Integration

## Goal

Describe how Star Office UI can be added later as the preferred visual shell while keeping the AI Command Center in control of execution state.

## Integration posture

Star Office UI should be treated as:

- a visual office shell
- a status dashboard
- a run-summary surface
- a human review aid

It should not be treated as:

- a task planner of record
- a worker launcher of record
- a file editor of record
- a spending authority

## Command center responsibilities

The command center keeps responsibility for:

- task lifecycle
- lock management
- run logging
- report generation
- approvals
- validation

## Dashboard responsibilities

The dashboard receives:

- agent status
- task status
- run summaries
- budget posture
- moderation or guardrail warnings

The dashboard must not:

- decide what work starts next
- spawn workers
- spend budget
- modify repository files

## Planned display model

Each visual agent card can show:

- display name
- role ID
- current mapped status
- latest task
- latest summary
- last update timestamp

## Status mapping

- `todo` -> `idle`
- `in_progress` -> `executing`
- `review` -> `syncing`
- `done` -> `idle`
- `failed` -> `error`
- research task -> `researching`
- writing/docs/content task -> `writing`

## Suggested initial payloads

- task counts by status
- current locks count
- most recent run log summaries
- most recent report summary
- agent display names and roles

## Future stack notes

- Antigravity/Codex can serve as the dev manager workspace for maintaining the command center.
- OpenClaw-style runtime ideas can influence future long-running loop design.
- NotebookLM-style knowledge workflows can help generate task context and prompt packs.
- OpenRouter can be added later as a model-routing layer if needed.
- Star Office UI remains the preferred visual shell target for now.

## Not implemented yet

- No Star Office UI installation
- No runtime wiring
- No API connections
- No dashboard-driven execution
