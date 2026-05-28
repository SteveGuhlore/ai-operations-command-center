# Tools Mastery

## Purpose

This folder contains tool-usage guidance for the AI Operations Command Center.

## Important note

Tool mastery is how agents learn to use tools consistently.

This is:

- documentation
- operational conditioning
- usage guidance
- safety guidance

It is not:

- API integration
- automatic runtime execution
- provider-specific implementation

## Role of this layer

Actual tool calls come later through provider adapters and permissions.

For now, this layer defines:

- what a tool is for
- which roles may use it
- what safe use looks like
- what bad use looks like
- when to escalate
