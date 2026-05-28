# Social Scheduler Usage Guide

## Purpose

Queue and plan external posting only when explicit approval exists.

## Allowed roles

- manager
- content_worker
- media_worker
- budget_worker

## Common safe tasks

- draft scheduling plans
- organize queue ideas
- document posting windows
- prepare approved content packages

## Forbidden tasks

- posting without approval
- real account actions without approval
- hidden paid distribution
- bypassing moderation

## Required inputs

- approved content set
- schedule window
- approval confirmation

## Expected outputs

- schedule summary
- queue plan
- approval state note

## Quality checklist

- posting remains approval-gated
- queue is clearly documented
- moderation state is known
- no hidden publishing occurs

## Failure modes

- missing approval
- unclear content status
- accidental real posting behavior
- account-side assumptions

## Escalation rules

- escalate if approval is missing
- stop if real posting would occur
- escalate if moderation state is incomplete

## Example good use

- draft a publish queue for later human approval

## Example bad use

- push live content automatically
