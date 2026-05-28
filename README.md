# AI Agent Command Center

One reusable command center for coordinating local AI coding workflows across projects.

## Default roles

- `manager` = `Atlas`, coordinator / reviewer
- `heavy_worker` = `Forge`, implementation-focused worker
- `debug_worker` = `Scout`, debugger / test-fixer / docs worker

These role IDs stay generic in tasks and scripts. The display names are stable labels for the humans using the command center.

## Future model mapping

Each role can later be mapped in configuration to Codex, MiniMax, Kimi, a Haiku-level model, or another provider/model pair. The foundation does not hard-code model providers yet.

## Framework

```text
Manager plans work
-> creates task specs
-> workers pick tasks
-> workers create lock files
-> task moves through statuses
-> workers execute / test / log
-> manager reviews
-> failures are requeued or escalated
-> cycle repeats
```

## Current stage

This folder is a generic foundation. It supports doctor checks, project/task validation, and dry-run task movement without requiring external project access.
