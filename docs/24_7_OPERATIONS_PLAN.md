# 24/7 Operations Plan

## Goal

Describe how the generic AI Command Center could support continuous operation planning without yet wiring any provider APIs or real automation actions into execution.

## Operating idea

The command center can be extended from a dry-run local batch system into a round-the-clock planning layer built around:

- stable role IDs
- readable display names
- explicit tool access rules
- budget and retry controls
- approval-gated external actions
- scheduled health checks and reporting

## Proposed role mix

- `Atlas` coordinates and reviews.
- `Forge` handles heavier implementation work.
- `Scout` handles validation, debugging, and reports.
- `Muse`, `Frame`, and `Echo` expand into content, media, and audio workflows.
- `Guard` enforces policy and moderation checks.
- `Ledger` tracks spend and threshold posture.

## Proposed tool mix

- Local workspace tools for code and file operations.
- Research tools for current information when explicitly allowed.
- Media and audio generation tools for asset creation.
- Social scheduling for external distribution, always behind approval.
- Cost and moderation tools for operational safety.

## Control model

1. Scheduled scans review queue state and system health.
2. Allowed roles prepare work inside their safe scope.
3. Guardrails and moderation block risky actions.
4. Budget tracking warns, escalates, or shuts work down as thresholds are crossed.
5. Human approval gates remain in place for external posting, destructive changes, real account actions, and overspend.

## Not wired yet

- No provider API connections.
- No real worker launch changes.
- No autonomous external posting.
- No automatic spending or account actions.

## Reference configs

- [agents.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\agents.example.yaml)
- [tools.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\tools.example.yaml)
- [guardrails.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\guardrails.example.yaml)
- [budgets.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\budgets.example.yaml)
- [schedules.example.yaml](C:\Users\sbattaglia\Downloads\AI Operations Command Center\config\schedules.example.yaml)
