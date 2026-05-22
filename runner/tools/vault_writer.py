from datetime import datetime
from pathlib import Path

if not globals().get("VAULT_DIR"):
    VAULT_DIR = Path(__file__).parent.parent.parent / "vault"

_OUTPUT_PREVIEW_CHARS = 500


def write_vault_session(task_id: str, role_id: str, result: dict) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = VAULT_DIR / "sessions" / today
    session_dir.mkdir(parents=True, exist_ok=True)

    status = "failed" if "error" in result else "done"
    output_preview = str(result.get("output", ""))[:_OUTPUT_PREVIEW_CHARS]

    content = (
        f"# {task_id} — {role_id}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Status: {status}\n"
        f"Tokens: {result.get('input_tokens', 0)} input / {result.get('output_tokens', 0)} output\n"
        f"Cost: ${result.get('cost_usd', 0.0):.4f}\n"
        f"Errors: {result.get('error', 'none')}\n"
        f"\n"
        f"## Output Preview\n"
        f"{output_preview}\n"
    )

    (session_dir / f"{task_id}.md").write_text(content, encoding="utf-8")
