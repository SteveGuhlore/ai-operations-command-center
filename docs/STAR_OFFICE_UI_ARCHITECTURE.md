# Star Office UI Architecture

## Goal

Prepare the AI Operations Command Center so Star Office UI can become the primary live visual shell without replacing the command center backend.

## System split

### Command center backend owns

- tasks
- locks
- logs
- reports
- budgets
- guardrails
- routing
- scheduling

### Star Office UI owns

- live office visualization
- agent activity dashboard
- status, queue, and revenue pod monitoring

## Core rule

The command center remains the source of truth. Star Office UI is a visual shell layered on top of command-center state.

## Agent cards

Each agent should be represented visually with:

- `role_id`
- `display_name`
- `office_status`
- `current_task`
- `pod_assignment`
- `model_label`
- `health_state`

## Revenue pod visualization

The dashboard state should present revenue pods as visible office units:

- Etsy
- Dropshipping
- Affiliate
- Short Form Video
- Digital Products
- Lead Gen
- Stock Research
- App/SaaS

## Status mapping

- `todo` -> `idle`
- `in_progress` -> `executing`
- `review` -> `syncing`
- `done` -> `idle`
- `failed` -> `error`

Task flavor overlays can later show:

- research task -> `researching`
- writing/docs/content task -> `writing`

## Future integration placeholders

- OpenRouter for model/provider routing
- Antigravity/Codex as dev manager workspace
- NotebookLM-style knowledge base for context generation
- scheduler/daemon for recurring updates

## Replaceable frontend rule

The backend must stay generic enough that Star Office UI could be replaced later without rewriting the task engine, locks, reports, or validation logic.
