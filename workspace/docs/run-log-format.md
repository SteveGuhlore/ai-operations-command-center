# Run Log Format

**Location:** `workspace/runs/<TASK-ID>-<worker-name>.md`

Run logs are created automatically by the launcher for every task execution (including dry runs).
They serve as the canonical audit trail for each task transition.

---

## Required Fields

| Field | Description |
|---|---|
| `Source task filename` | Full filename of the task file (e.g. `SAMPLE-002-heavy-worker-implementation-task.md`) |
| `Task id` | Short task identifier (e.g. `SAMPLE-002`) |
| `Assigned worker type` | Role slug (e.g. `heavy_worker`, `debug_worker`) |
| `Assigned worker display name` | Human-friendly name (e.g. `Forge`, `Scout`) |
| `Worker name` | Instance name used in log entries (e.g. `heavy-worker-dryrun-1`) |
| `Started` | Timestamp in `MM/DD/YYYY HH:MM:SS` format |
| `Starting status` | Task queue folder before execution (e.g. `todo`) |
| `Ending status` | Task queue folder after execution (e.g. `review`, `done`, `failed`) |
| `Lock created` | `yes` or `no` |
| `Lock released` | `yes` or `no` — must be `yes` unless the process crashed |

## Optional Body Section

After the required fields, a blank line separates free-form body content.
Worker output, AI responses, errors, and tool call results go here.

For dry runs, this section must contain:
```
Dry run only. No AI CLI was called.
```

For live runs, this section should contain:
- Summary of actions taken
- Files changed
- Commands run
- Results
- Risks/notes

---

## Consistency Rules

- All run log files **must** include `Assigned worker display name`. Logs missing this field are considered malformed.
- A log with `Lock created: yes` and `Lock released: no` indicates a potential orphaned lock — the `doctor.ps1` script checks for this condition.
- Ending status `failed` must include a reason in the body section.
