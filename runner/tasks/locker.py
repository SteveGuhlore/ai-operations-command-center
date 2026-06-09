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
            "pid": os.getpid(),  # lets the reaper distinguish a live run from a dead one
        }))
    return True


def lock_owner_alive(task_id: str) -> bool:
    """True if the lock exists and its owning process is still running. A worker thread that
    outlives its cycle's 12-min future timeout keeps executing (threads can't be killed), so
    lock/file age alone can't prove a task is dead — the owner pid can."""
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    try:
        pid = json.loads(lock_path.read_text(encoding="utf-8")).get("pid")
        if not pid:
            return False
        os.kill(int(pid), 0)  # signal 0: existence check, sends nothing
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def release_lock(task_id: str) -> None:
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()


def is_locked(task_id: str) -> bool:
    return (LOCKS_DIR / f"{task_id}.lock").exists()
