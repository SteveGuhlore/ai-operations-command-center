# Context Bundle Standard

## Goal

Define how selected project context should be copied or summarized into `workspace/context` so agents can work with a bounded view instead of absorbing an entire project.

## Why bounded context matters

Agents should not be given the whole project by default. Selected context bundles:

- reduce noise
- reduce cost
- improve task focus
- make file ownership clearer
- improve reviewability

## What belongs in a context bundle

- short project overview
- current status summary
- roadmap or backlog summary
- relevant file map
- key validation commands
- specific files or excerpts needed for the task batch

## What should not be copied blindly

- full repositories
- secrets
- environment files
- unrelated history
- large binary assets unless directly needed

## Bundle structure

Suggested structure under `workspace/context`:

- `PROJECT-OVERVIEW.md`
- `CURRENT-STATUS.md`
- `ROADMAP-SUMMARY.md`
- `FILE-MAP.md`
- `TEST-COMMANDS.md`
- task-specific notes or excerpts

## Agent reading rule

Agents should read:

- the task file
- the selected context bundle
- only the files explicitly allowed or needed

Agents should not absorb the whole project unless a later approved step explicitly broadens scope.

## Stop conditions

- Stop if the context bundle becomes a copy of the whole project.
- Stop if secrets or credentials would be copied.
- Stop if a worker needs files outside the approved context and allowed file list without escalation.
