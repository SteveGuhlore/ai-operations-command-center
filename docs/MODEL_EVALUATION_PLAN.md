# Model Evaluation Plan

## Goal

Define how the command center will later evaluate candidate models for each generic role without hard-coding provider choices into the foundation.

## Stable roles and display names

- `manager` = `Atlas`
- `heavy_worker` = `Forge`
- `debug_worker` = `Scout`

The role IDs remain stable in tasks and scripts. Provider/model mapping should be configured separately later.

## Initial mapping philosophy

- `Atlas` should favor strong review, planning, and risk-spotting behavior.
- `Forge` should favor reliable implementation throughput on bounded coding tasks.
- `Scout` should favor low-cost debugging, validation, summaries, and retry loops.

Possible future mappings include Codex, Kimi, MiniMax, Haiku-level models, or other providers, but none are hard-coded here.

## Scout A/B evaluation plan

`Scout` is a strong candidate for comparative testing between MiniMax and Haiku-level models because it handles repetitive debugging and reporting tasks where cost and retry behavior matter.

Run A/B trials on a shared set of `debug_worker` tasks and measure:

- Cost per completed task
- Average retries per completed task
- Task success rate
- Bug-introduction rate

## Suggested test design

1. Use the same task templates and acceptance criteria for both candidates.
2. Keep file ownership rules and stop conditions identical.
3. Compare results across multiple task types:
   - validation fixes
   - simple failing test repair
   - docs and report updates
   - import/path cleanup
4. Review outputs with the same manager rubric.

## Success criteria

A candidate is a better `Scout` mapping if it:

- finishes more tasks within retry limits,
- introduces fewer regressions,
- keeps cost lower for similar success,
- produces cleaner reports and escalation notes.

## Guardrails

- Do not wire provider APIs into the foundation during evaluation planning.
- Do not change the generic role IDs while testing providers.
- Do not infer winner status from a single batch.
