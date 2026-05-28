# Cost Tracker Usage Guide

## Purpose

Track cost, retries, thresholds, and usage posture.

## Allowed roles

- manager
- budget_worker
- guard_worker

## Common safe tasks

- summarize usage
- compare threshold posture
- report cost trends
- prepare shutdown alerts

## Forbidden tasks

- overriding budgets without approval
- hiding overages
- making spend decisions without escalation
- fake or unsupported cost reporting

## Required inputs

- usage records
- threshold values
- role or pod context

## Expected outputs

- budget summary
- warnings
- escalation notes
- recommended next step

## Quality checklist

- numbers are clear
- warnings are explicit
- uncertainty is visible
- shutdown state is obvious

## Failure modes

- incomplete spend data
- vague reporting
- threshold confusion
- hidden overruns

## Escalation rules

- escalate threshold crossings
- escalate missing data
- stop if work should pause but the system is still trying to continue

## Example good use

- produce a clear threshold report for Ledger

## Example bad use

- suggest continuing spend with no approval
