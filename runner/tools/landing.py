# runner/tools/landing.py
import json
import re
from datetime import datetime
from pathlib import Path

LANDINGS_DIR = Path(__file__).parent.parent.parent / "workspace" / "landings"

# slug is interpolated into a filename — restrict it so a crafted slug like
# "../logs/x" can't read or overwrite .json files outside workspace/landings.
_SLUG_RE = re.compile(r"^[a-z0-9-]{1,64}$")


def _path(slug: str) -> Path:
    if not _SLUG_RE.match(slug or ""):
        raise ValueError(f"invalid landing slug: {slug!r}")
    return LANDINGS_DIR / f"{slug}.json"


def landing_exists(slug: str) -> bool:
    try:
        return _path(slug).exists()
    except ValueError:
        return False


def read_landing_state(slug: str) -> dict:
    try:
        p = _path(slug)
    except ValueError:
        return {}
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
