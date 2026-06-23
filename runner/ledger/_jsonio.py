"""Single source for crash-safe ledger IO: fail-soft JSON reads + atomic writes.

The ledger/tools layer had this exact read-modify-write pair copy-pasted a dozen times —
a "return []/{} on any error" reader and budget.py's tmp-sibling + os.replace writer.
Consolidating it here keeps every ledger's torn-write and corrupt-read behavior identical.
Imports NOTHING from the ledger/tools modules that use it (avoids import cycles).
"""

import json
import os
from pathlib import Path
from typing import Any


def load_list(path) -> list:
    """Read a JSON list; return [] on missing/empty/corrupt/OSError. Never raises."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return []


def load_dict(path) -> dict:
    """Read a JSON dict; return {} on missing/empty/corrupt/OSError. Never raises."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        return {}


def atomic_write_json(path, data: Any, **dumps_kwargs) -> None:
    """Crash-safe write: a concurrent reader (or a crash mid-write) must never see a torn
    JSON file. mkdir parents, write to a temp sibling whose name carries os.getpid(), then
    os.replace onto the target (atomic on the same filesystem, incl. Windows). `dumps_kwargs`
    pass through to json.dumps so each caller keeps its exact on-disk shape (indent/sort_keys)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, **dumps_kwargs), encoding="utf-8")
    os.replace(tmp, path)
