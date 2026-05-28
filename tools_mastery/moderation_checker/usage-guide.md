# Moderation Checker Usage Guide

## Purpose

Check whether content, media, or actions meet moderation and policy requirements before release or risky handling.

## Allowed roles

- manager
- guard_worker
- content_worker
- media_worker
- audio_worker

## Common safe tasks

- review publishable content
- flag risky media
- verify approval readiness
- support policy checks

## Forbidden tasks

- overriding failed moderation without approval
- silent acceptance of risky content
- bypassing guardrails
- using moderation as a substitute for human approval where required

## Required inputs

- content or media summary
- moderation target
- policy context if needed

## Expected outputs

- pass/fail or caution result
- reasons
- approval requirements
- escalation recommendation

## Quality checklist

- reasons are explicit
- risk is not hidden
- outputs are conservative
- approval needs are visible

## Failure modes

- vague moderation reasoning
- false confidence
- ignored safety concerns
- unclear approval state

## Escalation rules

- escalate uncertainty
- escalate any unsafe publishable output
- stop when approval is required and missing

## Example good use

- flag risky content before any scheduling plan

## Example bad use

- allow questionable content through with no explanation
