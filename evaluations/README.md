# Evaluations

## Purpose

This folder stores structured evaluation records for agent outputs, task scores, pod scores, model comparisons, failure patterns, and retry effectiveness.

## Important note

Evaluation is how agents improve without true model training.

This is:

- operational evaluation
- review structure
- scoring history
- model comparison support
- routing support

It is not:

- frontier-model training
- automatic runtime control
- credential storage

## Design goal

Evaluations should be structured, comparable, and reusable.

## Safety rule

Do not store secrets, credentials, private account information, or raw sensitive data in evaluation records.
