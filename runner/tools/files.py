from pathlib import Path

WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspace"


def _safe_path(relative: str) -> Path | None:
    target = (WORKSPACE_DIR / relative).resolve()
    if not str(target).startswith(str(WORKSPACE_DIR.resolve())):
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


def list_files(directory: str = ".") -> dict:
    safe = _safe_path(directory)
    if safe is None:
        return {"error": f"Path outside workspace: {directory}"}
    if not safe.is_dir():
        return {"error": f"Not a directory: {directory}"}
    return {"files": [f.name for f in sorted(safe.iterdir())]}


TOOL_SPEC = {
    "name": "file_editor",
    "description": "Read, write, or list files inside the workspace directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "list"]},
            "path": {"type": "string", "description": "Relative path inside workspace"},
            "content": {"type": "string", "description": "Content to write (only for write action)"},
        },
        "required": ["action", "path"],
    }
}


def file_editor(action: str, path: str, content: str = "") -> dict:
    if action == "read":
        return read_file(path)
    if action == "write":
        return write_file(path, content)
    if action == "list":
        return list_files(path)
    return {"error": f"Unknown action: {action}"}
