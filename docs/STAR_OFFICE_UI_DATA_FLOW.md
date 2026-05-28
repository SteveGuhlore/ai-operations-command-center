# Star Office UI Data Flow

## Goal

Describe how dashboard state should move from the AI Operations Command Center into Star Office UI.

## Export-first design

The command center should export a full office-state JSON file first. That exported file is the handoff artifact for the visual shell.

## Export payload

`dashboard-export-state.ps1` should export:

- agents
- statuses
- current tasks
- task counts
- locks
- recent runs
- revenue pods
- alerts
- daemon state placeholder
- budget state placeholder

## Current transport modes

Two future delivery modes are planned:

1. Star Office UI polls `dashboard-state.json`
2. `dashboard-push.ps1` pushes state updates into the visual shell

## Current safe mode

Right now the safe mode is:

- export local JSON
- keep the file in `workspace/dashboard`
- do not connect real APIs
- do not let the dashboard write back into the backend

## Direction of flow

1. Command center reads tasks, locks, runs, reports, and config.
2. `dashboard-export-state.ps1` builds a read-only office-state payload.
3. `dashboard-push.ps1` becomes the future bridge into Star Office UI.
4. Star Office UI renders office state for humans.

## Forbidden reverse flow

The visual shell must not:

- decide tasks
- spawn workers
- edit files
- spend budget
- bypass guardrails

## Future placeholders

- OpenRouter can later inform model labels and routing summaries.
- Antigravity/Codex can maintain the dev manager workspace.
- NotebookLM-style knowledge systems can enrich context summaries.
- scheduler/daemon can trigger recurring exports or pushes later.
