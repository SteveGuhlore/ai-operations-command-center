# Memory Usage Rules

## Goal

Define how memory should be stored and later reused inside the AI Operations Command Center.

## Core principle

Memory is structured operational history, not model fine-tuning.

## Safe usage rules

- memory files should contain reviewed summaries, not raw uncontrolled dumps
- memory should avoid secrets, credentials, private account information, and raw sensitive data
- only approved memory should later be used as agent context
- memory should stay readable and auditable

## Role guidance

- `Atlas` decides what memory becomes reusable
- `Guard` can flag unsafe, weak, or risky memory
- `Ledger` can use pod performance memory for cost and revenue analysis

## Future use

Agents can later read approved memory files as context, but runtime retrieval is not part of the current foundation.

## What should not go into memory

- API keys
- secrets
- real account details
- raw private personal information
- uncontrolled external data dumps
