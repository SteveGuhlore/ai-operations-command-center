# Memory System Foundation

## Goal

Describe the early memory layer that can support worker playbooks, evaluation, and future routing decisions.

## Important note

This is operational conditioning, memory design, and review infrastructure. It is not frontier-model training.

## What should be remembered

- successful outputs
- failed outputs
- retry history
- pod performance
- reusable context bundles
- shared knowledge
- future long-term learning datasets

## Successful outputs

Capture examples of:

- strong task completion
- clean summaries
- good escalation behavior
- effective formatting
- useful reports

These become reference patterns for future workers and reviewers.

## Failed outputs

Capture examples of:

- scope drift
- unsafe behavior
- weak summaries
- repeated failed retries
- low-quality pod outputs

Failed outputs are just as important as successful ones because they define what to avoid.

## Retry history

Track:

- how many retries happened
- why retries happened
- whether retries improved quality
- where retries should have escalated sooner

## Pod performance

Memory should preserve:

- which pods produce useful outputs
- which pods create repeated low-value work
- which task types consume too much cost or review time

## Reusable context bundles

Good context bundles should be reusable where possible so agents do not need to reload or rediscover the same background repeatedly.

## Shared knowledge

Shared knowledge can include:

- role playbooks
- formatting standards
- common failure modes
- known good workflows
- recurring approval patterns

## Future long-term learning datasets

Later, the command center may collect structured examples for:

- model comparison
- routing experiments
- evaluation model ideas
- optional fine-tuning datasets much later

That future dataset work should happen only after memory, scoring, and review systems are already useful.
