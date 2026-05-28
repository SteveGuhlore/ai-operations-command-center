# Evaluation System Foundation

## Goal

Describe the early evaluation layer that will help the command center measure worker quality, retry value, and pod usefulness.

## Important note

This is operational conditioning and evaluation design, not frontier-model training.

## Core evaluation areas

- output scoring
- QA/review flow
- retry effectiveness
- model comparison
- cost vs quality
- performance tracking
- pod success metrics

## Output scoring

Outputs should be scored on:

- clarity
- correctness
- safety
- scope control
- reviewability
- escalation quality

## QA/review flow

A basic evaluation flow should be:

1. worker completes output
2. reviewer checks against rubric
3. issues are marked as acceptable, weak, or unsafe
4. retry or escalation is chosen
5. result is stored for future memory

## Retry effectiveness

Evaluation should ask:

- did the retry improve quality?
- did retries waste budget?
- should the task have escalated earlier?
- which roles benefit from retries and which do not?

## Model comparison

Later model comparison should focus on:

- task success
- retry count
- quality score
- bug or failure rate
- reviewer confidence

## Cost vs quality

The system should compare:

- cost per useful output
- cost per accepted output
- cost per failed or retried output

The cheapest model is not always best if it creates too much review overhead.

## Performance tracking

Track performance at several levels:

- by role
- by task type
- by pod
- by model label
- by retry pattern

## Pod success metrics

Evaluation should measure whether pods produce:

- reviewable outputs
- useful assets
- repeatable workflows
- good cost posture
- better downstream business signals later

## Why this matters early

Prompt quality, memory, evaluation, and routing improvements matter more at the start than custom model training.

Real fine-tuning is optional and should come much later, only if the operational evidence says it is worth it.
