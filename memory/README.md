# Memory

## Purpose

This folder stores structured operational history for the AI Operations Command Center.

## Important note

This is not model fine-tuning.

It is:

- operational memory
- review history
- reusable examples
- retry history
- pod performance history
- context bundle storage
- model evaluation notes

## Core rule

Memory files are for approved structured context only. They should avoid secrets, credentials, private account information, and raw sensitive data.

## Memory ownership

- `Atlas` decides what memory becomes reusable.
- `Guard` can flag unsafe, low-quality, or risky memory.
- `Ledger` can use pod performance memory for cost and revenue analysis later.
- agents may later read approved memory files as context, but runtime retrieval is not built yet.
