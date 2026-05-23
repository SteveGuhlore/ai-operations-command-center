import logging
from datetime import datetime
from pathlib import Path

VAULT_DIR = Path(__file__).parent.parent.parent / "vault"

_log = logging.getLogger(__name__)


def write_vault_session(task_id: str, role_id: str, result: dict, *, vault_dir=None) -> None:
    base = Path(vault_dir) if vault_dir else VAULT_DIR
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        session_dir = base / "sessions" / today
        session_dir.mkdir(parents=True, exist_ok=True)

        status = "failed" if "error" in result else "done"
        output = str(result.get("output", ""))
        safe_id = task_id.replace("/", "_").replace("\\", "_").replace(":", "_")

        content = (
            f"# {task_id} — {role_id}\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Status: {status}\n"
            f"Tokens: {result.get('input_tokens', 0)} input / {result.get('output_tokens', 0)} output\n"
            f"Cost: ${result.get('cost_usd', 0.0):.4f}\n"
            f"Errors: {result.get('error', 'none')}\n"
            f"\n"
            f"## Output\n"
            f"{output}\n"
        )

        (session_dir / f"{safe_id}.md").write_text(content, encoding="utf-8")
    except OSError as exc:
        _log.warning("vault_writer: could not write session for %s: %s", task_id, exc)
