# Visual UI Strategy

## Goal

Define how a visual dashboard can sit on top of the AI Command Center without becoming the system of record.

## Source of truth

The AI Command Center remains the source of truth for:

- task files
- task status folders
- locks
- run logs
- reports
- validation results

The visual UI should only reflect that state.

## Visual layer role

The visual dashboard is a status and presentation layer only. It may display:

- agent status
- task status
- run summaries
- guardrail alerts
- budget posture
- batch summaries

It must not:

- decide tasks
- spawn workers
- spend money
- edit files

## Planned visual agents

- `Atlas` = manager
- `Forge` = heavy worker
- `Scout` = debug worker
- `Muse` = content worker
- `Frame` = image/video worker
- `Echo` = audio worker
- `Guard` = moderation worker
- `Ledger` = budget/audit worker

## Future optional office agent

- `Tony Stocks` = `market_research_worker`

Tony Stocks is a future optional specialist profile for a project-specific office setup. It is not part of the core required team and should remain disabled until a real project profile and explicit permissions are added later.

## Status mapping

- `todo` -> `idle`
- `in_progress` -> `executing`
- `review` -> `syncing`
- `done` -> `idle`
- `failed` -> `error`
- research task -> `researching`
- writing/docs/content task -> `writing`

## Data flow

1. The command center updates task folders, logs, and reports.
2. A read-only dashboard push layer collects summarized state.
3. The visual UI renders that state for humans.
4. Humans still approve risky actions through the command center rules.

## Why this split matters

Keeping the command center as the source of truth preserves:

- auditability
- file-based recovery
- local validation
- approval boundaries
- model/provider portability

The visual shell should improve clarity, not control.

## Future stack notes

- Antigravity/Codex can be used as a dev manager workspace.
- OpenClaw-style runtime can inspire long-running worker loops later.
- NotebookLM-style knowledge base can generate prompts and context later.
- OpenRouter can route models later.
- Star Office UI is the preferred visual shell for now.
