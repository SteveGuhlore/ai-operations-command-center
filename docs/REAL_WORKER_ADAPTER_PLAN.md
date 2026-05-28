# Real Worker Adapter Plan

## Goal

Describe what the real worker adapter layer must do later, without implementing it yet.

## Responsibilities

A real worker adapter should:

- map generic role IDs to provider/model selections
- preserve stable display names
- distinguish dry-run from real-run mode
- enforce retry limits
- record run summaries back into the command center
- support escalation from one role to another
- avoid secrets in files

## Required behavior

- Use generic role IDs such as `manager`, `heavy_worker`, `debug_worker`, and others.
- Read validated config rather than hard-coded providers.
- Write run summaries and outcomes into `workspace/runs`.
- Respect `AllowRealRun` or equivalent explicit gating.
- Fail safely when credentials or provider settings are missing.

## Not allowed

- writing API keys into project files
- bypassing validation
- bypassing lock creation
- bypassing task ownership
- bypassing approval gates

## Stop conditions

- Stop if credentials would be written to disk.
- Stop if the adapter would launch real work without explicit approval.
- Stop if the adapter cannot log outcomes back to the command center.
