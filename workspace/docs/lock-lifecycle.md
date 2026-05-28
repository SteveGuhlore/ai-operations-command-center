# Lock Lifecycle

Lock files live in `workspace/locks/<TASK-ID>.lock`.

They are JSON objects with three fields:
```json
{
  "task_id": "SAMPLE-002",
  "agent_role": "heavy_worker",
  "acquired_at": 1779418619.4188535
}
```

---

## Lifecycle States

```
[task claimed by worker]
        |
        v
  lock file created  ──→  worker executes task  ──→  lock file deleted
                                                       (lock released)
```

A lock file that survives after a run log shows `Lock released: yes` is an
**orphaned lock** — the file was not cleaned up correctly.

---

## Orphaned Lock Detection

The `doctor.ps1` script identifies orphaned locks by:
1. Listing all files in `locks/`.
2. For each lock, finding the corresponding run log in `runs/`.
3. If the run log shows `Lock released: yes` but the lock file still exists → **orphan warning**.
4. If no run log exists for the lock at all → **unknown lock warning**.

### Known orphaned locks as of SAMPLE-002

| Lock file | Last run log | Status |
|---|---|---|
| `SAMPLE-002.lock` | `SAMPLE-002-heavy-worker-dryrun-1.md` (released: yes) | Orphaned |
| `POD-SOC-001.lock` | No matching run log in `runs/` | Unknown |

These should be manually deleted or cleared by running `doctor.ps1 -Fix`.

---

## Rules

- A task **must not** be worked on by two agents simultaneously — the lock prevents this.
- A lock is only valid for the `agent_role` listed inside it.
- Lock acquisition timestamp (`acquired_at`) is a Unix epoch float.
- If a lock is older than 24 hours and no active process holds it, it is considered stale.
