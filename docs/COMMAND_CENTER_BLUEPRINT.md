# Command Center Blueprint

## Goal

Create a reusable local AI development pipeline that can run large batches of development work with less manual babysitting.

## Operating loop

```text
Codex Manager
→ reads project profile
→ reads roadmap/backlog/status
→ creates batch
→ assigns task types
→ launches/instructs workers
→ reviews results
→ requeues failures
→ writes final batch report
```

```text
Worker
→ picks task from todo
→ creates lock
→ moves task to in_progress
→ collects context
→ executes assigned work
→ runs checks
→ writes run log
→ moves task to review/done/failed
→ releases lock
→ takes next task
```

## Why this structure

- Task files keep instructions specific.
- Lock files prevent duplicate work.
- Status folders show progress.
- Logs create an audit trail.
- Project profiles make this reusable across projects.
- Codex reviews instead of letting workers freely merge.
