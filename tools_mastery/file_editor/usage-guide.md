# File Editor Usage Guide

## Purpose

Create and edit local files inside the approved workspace.

## Allowed roles

- manager
- heavy_worker
- debug_worker
- content_worker
- media_worker

## Common safe tasks

- update docs
- edit templates
- patch scripts
- create structured config examples

## Forbidden tasks

- edits outside allowed files
- secret insertion
- destructive file operations without approval
- changing files outside scope

## Required inputs

- target files
- intended outcome
- scope boundaries

## Expected outputs

- changed file summary
- what was updated
- risks or notes

## Quality checklist

- edits are minimal and readable
- file ownership is respected
- no secrets are added
- output is easy to review

## Failure modes

- scope drift
- editing the wrong file
- formatting inconsistency
- hidden risky changes

## Escalation rules

- escalate if more files are needed
- escalate if a forbidden file would be touched
- stop if the request requires secrets or external actions

## Example good use

- update a validator script and matching docs

## Example bad use

- rewrite unrelated files because they seem “close enough”
