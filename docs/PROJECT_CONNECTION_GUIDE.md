# Project Connection Guide

## Goal

Explain how a future project should be connected to the AI Operations Command Center through a project profile without changing the command center’s role as the source of truth.

## Connection model

A future project should be connected through a profile file, not by hard-coding paths into scripts or tasks.

The project profile should define:

- project name
- placeholder or real project path
- read-first context files
- validation commands
- smoke commands
- forbidden changes
- autonomy level
- retry limits
- parallel worker limits

## Safe connection sequence

1. Create a new project profile from the template.
2. Keep the project path in placeholder mode until the target machine is ready.
3. Validate the profile before any task generation.
4. Copy or summarize only selected context into `workspace/context`.
5. Create project-specific tasks that point to the selected context bundle.
6. Keep all task movement, locks, logs, and reports inside the command center.

## Source-of-truth rule

The command center remains the source of truth for:

- task state
- run history
- approvals
- dry-run vs real-run gating

The connected project is the work target, not the orchestration layer.

## Stop conditions

- Stop if the project profile fails validation.
- Stop if the profile would require credentials in files.
- Stop if the connection step tries to bypass `workspace/context`.
- Stop if the task set becomes broader than the selected context bundle supports.
