from pathlib import Path

# Root of the project — agents need to read/write both workspace/ and vault/
PROJECT_ROOT = Path(__file__).parent.parent.parent


def _safe_path(relative: str) -> Path | None:
    root = PROJECT_ROOT.resolve()
    target = (root / relative).resolve()
    # is_relative_to is a true parent-membership check; the old str.startswith
    # test let sibling dirs sharing the prefix (…/AI Operations Command Center-backup)
    # escape the repo root.
    if target != root and not target.is_relative_to(root):
        return None
    return target


def read_file(path: str) -> dict:
    safe = _safe_path(path)
    if safe is None:
        return {"error": f"Path outside workspace: {path}"}
    if not safe.exists():
        return {"error": f"File not found: {path}"}
    try:
        return {"content": safe.read_text(encoding="utf-8")}
    except OSError as exc:
        return {"error": str(exc)}


def write_file(path: str, content: str) -> dict:
    safe = _safe_path(path)
    if safe is None:
        return {"error": f"Path outside workspace: {path}"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(safe)}
    except OSError as exc:
        return {"error": str(exc)}


def append_file(path: str, content: str) -> dict:
    safe = _safe_path(path)
    if safe is None:
        return {"error": f"Path outside workspace: {path}"}
    try:
        safe.parent.mkdir(parents=True, exist_ok=True)
        with safe.open("a", encoding="utf-8") as f:
            if safe.exists() and safe.stat().st_size > 0:
                existing = safe.read_bytes()
                if existing and existing[-1:] != b"\n":
                    f.write("\n")
            f.write(content)
        return {"success": True, "path": str(safe)}
    except OSError as exc:
        return {"error": str(exc)}


def list_files(directory: str = ".") -> dict:
    safe = _safe_path(directory)
    if safe is None:
        return {"error": f"Path outside workspace: {directory}"}
    if not safe.is_dir():
        return {"error": f"Not a directory: {directory}"}
    return {"files": [f.name for f in sorted(safe.iterdir())]}


TOOL_SPEC = {
    "name": "file_editor",
    "description": "Read, write, append, or list files in the project (workspace/, vault/, agents/, etc.).",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "append", "list"]},
            "path": {"type": "string", "description": "Relative path inside workspace"},
            "content": {"type": "string", "description": "Content to write or append (for write/append actions)"},
        },
        "required": ["action", "path"],
    }
}


def file_editor(action: str, path: str, content: str = "") -> dict:
    if action == "read":
        return read_file(path)
    if action == "write":
        return write_file(path, content)
    if action == "append":
        return append_file(path, content)
    if action == "list":
        return list_files(path)
    return {"error": f"Unknown action: {action}"}
