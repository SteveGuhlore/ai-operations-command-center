# Evaluation Usage Rules

## Goal

Define how evaluations should be stored and later used inside the AI Operations Command Center.

## Core principle

Evaluation is how agents improve without true model training.

## Role guidance

- `Atlas` uses evaluations to route tasks better
- `Guard` uses evaluations to catch risky outputs
- `Ledger` uses evaluations to compare cost vs quality
- `Scout` uses evaluations to identify repeat failures

## Structure rules

Evaluations should be:

- structured
- comparable
- reusable
- reviewable

## Safety rules

- do not store secrets
- do not store credentials
- do not store private account data
- do not store raw sensitive information

## Future use

These evaluation files can later support:

- routing improvements
- retry policy improvements
- model comparison
- pod prioritization

Runtime scoring and automated retrieval are not built yet.
