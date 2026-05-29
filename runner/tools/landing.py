# runner/tools/landing.py
import json
from datetime import datetime
from pathlib import Path

LANDINGS_DIR = Path(__file__).parent.parent.parent / "workspace" / "landings"


def _path(slug: str) -> Path:
    return LANDINGS_DIR / f"{slug}.json"


def landing_exists(slug: str) -> bool:
    return _path(slug).exists()


def read_landing_state(slug: str) -> dict:
    p = _path(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_landing_state(slug: str, status: str, **extra) -> dict:
    """Upsert the landing-state file. Merges extra fields (payment_link_url,
    public_url, deployed_at) over any existing state."""
    LANDINGS_DIR.mkdir(parents=True, exist_ok=True)
    state = read_landing_state(slug)
    state["slug"] = slug
    state["status"] = status
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state.update(extra)
    _path(slug).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
