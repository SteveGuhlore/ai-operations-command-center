# Reddit Framework Mapping

Original-style setup:

```text
launch grid
├─ clean old locks/logs
├─ check ready tasks
├─ open worker panes
└─ start autonomous agents
```

Our Windows-first setup:

```text
scripts/safe-launch.ps1
├─ runs doctor checks
├─ validates project profile
├─ validates tasks
├─ blocks unsafe real launch
└─ calls scripts/launch-batch.ps1
```

Original-style worker loop:

```text
pick task
→ create lock
→ move to In Progress
→ collect context
→ run AI coding agent
→ test / commit
→ parse result
→ update task
→ release lock
→ next task
```

Our local version:

```text
pick task from workspace/tasks/todo
→ create workspace/locks/TASK.lock
→ move task to workspace/tasks/in_progress
→ collect docs/context from project profile
→ call or manually paste into assigned AI agent
→ run project test commands
→ write workspace/runs/TASK-worker.md
→ move task to review/done/failed
→ release lock
→ next task
```

Linear can be added later. Local Markdown tasks are simpler for the first version.
