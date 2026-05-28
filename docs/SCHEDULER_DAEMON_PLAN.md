# Scheduler Daemon Plan

## Goal

Describe what a future scheduler or daemon layer must do later, without implementing it now.

## Responsibilities

A future scheduler or daemon should:

- run heartbeat checks
- scan queues on a schedule
- detect stale locks or stalled tasks
- generate recurring summaries
- support crash recovery
- respect stop and shutdown controls

## Safe operating model

The scheduler should begin as a low-risk reporting and queue-check layer before it is ever allowed to trigger more autonomous actions.

## Required safeguards

- do not bypass `doctor.ps1`
- do not bypass validators
- do not override budget or guardrails
- do not start real workers without an explicit approved mode
- preserve logs for each scheduled action

## Crash recovery expectations

- detect leftover locks
- detect tasks stuck in `in_progress`
- alert or write reports instead of improvising risky recovery

## Stop conditions

- Stop if validation is failing.
- Stop if locks remain unexpectedly.
- Stop if budget or guardrail state says work should pause.
- Stop if a scheduler action would publish, spend, or connect externally without approval.
