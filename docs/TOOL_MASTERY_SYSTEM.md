# Tool Mastery System

## Goal

Describe how the command center will teach agents to use tools consistently before real provider-backed tool execution exists.

## Core idea

Tool mastery is how agents learn to use tools consistently.

This is documentation and operational conditioning, not API integration.

## What this layer does

- defines safe tool usage expectations
- clarifies allowed roles
- explains failure modes
- standardizes escalation rules
- gives examples of good and bad use

## What this layer does not do

- connect APIs
- execute provider-backed tool calls
- bypass permissions
- grant runtime access automatically

## Future runtime note

Actual tool calls come later through provider adapters and permissions.

## Relationship to evaluation

Tool mastery guides can later support:

- better worker prompts
- stronger reviews
- tool-use scoring
- safer runtime adapters
