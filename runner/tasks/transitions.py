# runner/tasks/transitions.py
import re
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"

_STATUS_RE = re.compile(r"(^status:\s*)(\w+)", re.MULTILINE)


def move_task(task_id: str, from_status: str, to_status: str) -> Path:
    src_dir = TASKS_DIR / from_status
    dst_dir = TASKS_DIR / to_status
    dst_dir.mkdir(parents=True, exist_ok=True)

    matches = list(src_dir.glob(f"*{task_id}*.md"))
    if not matches:
        # Task already moved by a concurrent runner — treat as claimed, not a crash
        dst_matches = list(dst_dir.glob(f"*{task_id}*.md"))
        if dst_matches:
            return dst_matches[0]
        raise FileNotFoundError(f"Task {task_id} not found in {from_status}/ or {to_status}/")

    src = matches[0]
    content = _STATUS_RE.sub(f"\\g<1>{to_status}", src.read_text(encoding="utf-8"))
    dst = dst_dir / src.name
    dst.write_text(content, encoding="utf-8")
    src.unlink()
    return dst


def write_task_output(task_id: str, output: str, status: str) -> None:
    task_dir = TASKS_DIR / status
    matches = list(task_dir.glob(f"*{task_id}*.md"))
    if not matches:
        return
    path = matches[0]
    content = path.read_text(encoding="utf-8")
    path.write_text(content + f"\n\n## Agent Output\n\n{output}\n", encoding="utf-8")
