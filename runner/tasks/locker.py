import json
import os
import time
from pathlib import Path

LOCKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "locks"


def acquire_lock(task_id: str, agent_role: str) -> bool:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    # Atomic create-or-fail: a plain exists()-then-write is a TOCTOU race — two overlapping
    # cycles (e.g. cron + a dashboard /api/trigger) could both see "no lock" and both run the
    # same task, double-spending API budget. O_CREAT|O_EXCL makes the winner unambiguous; the
    # loser gets FileExistsError.
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "task_id": task_id,
            "agent_role": agent_role,
            "acquired_at": time.time(),
        }))
    return True


def release_lock(task_id: str) -> None:
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()


def is_locked(task_id: str) -> bool:
    return (LOCKS_DIR / f"{task_id}.lock").exists()
