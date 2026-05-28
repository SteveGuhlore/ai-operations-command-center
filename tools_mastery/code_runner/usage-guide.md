# Code Runner Usage Guide

## Purpose

Run local checks, scripts, and bounded commands inside the workspace.

## Allowed roles

- manager
- heavy_worker
- debug_worker
- guard_worker
- budget_worker

## Common safe tasks

- run validators
- run local checks
- inspect command results
- verify dry-run behavior

## Forbidden tasks

- destructive file operations without approval
- external side-effect actions
- real account actions
- hidden credential handling

## Required inputs

- clear command target
- expected safe scope
- working directory

## Expected outputs

- command summary
- result status
- key output or failure note

## Quality checklist

- command scope is clear
- action stays local
- result is summarized accurately
- risky commands are blocked or escalated

## Failure modes

- invalid working directory
- destructive command request
- unclear side effects
- environment mismatch

## Escalation rules

- escalate destructive or high-risk commands
- escalate if external effects are possible
- stop if credentials or real integrations are required

## Example good use

- run `doctor.ps1` and summarize the result

## Example bad use

- run an unbounded destructive cleanup without approval
