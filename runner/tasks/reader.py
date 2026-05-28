import re
from pathlib import Path
import yaml

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def parse_task_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(f"Invalid task format: {path}")
    frontmatter = yaml.safe_load(match.group(1))
    frontmatter["body"] = match.group(2).strip()
    frontmatter["file_path"] = str(path)
    return frontmatter


import logging as _logging
_log = _logging.getLogger(__name__)


def read_todo_tasks() -> list[dict]:
    todo_dir = TASKS_DIR / "todo"
    tasks = []
    for f in sorted(todo_dir.glob("*.md")):
        try:
            tasks.append(parse_task_file(f))
        except Exception as exc:
            _log.warning("Skipping malformed task file %s: %s", f.name, exc)
    return tasks
