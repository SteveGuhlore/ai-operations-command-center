import json
import time
from pathlib import Path

LOCKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "locks"


def acquire_lock(task_id: str, agent_role: str) -> bool:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        return False
    lock_path.write_text(json.dumps({
        "task_id": task_id,
        "agent_role": agent_role,
        "acquired_at": time.time(),
    }), encoding="utf-8")
    return True


def release_lock(task_id: str) -> None:
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()


def is_locked(task_id: str) -> bool:
    return (LOCKS_DIR / f"{task_id}.lock").exists()
