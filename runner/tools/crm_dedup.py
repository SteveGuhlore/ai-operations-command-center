from pathlib import Path

CRM_FILE = Path(__file__).parent.parent.parent / "vault" / "outreach" / "crm.md"


def dedup_crm() -> int:
    """Remove duplicate CRM rows by business name (case-insensitive). Keeps first occurrence.
    Returns the number of rows removed."""
    if not CRM_FILE.exists():
        return 0

    lines = CRM_FILE.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    removed = 0

    for line in lines:
        if not line.startswith("|") or line.startswith("|---") or "Business" in line[:30]:
            out.append(line)
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        name = parts[0].lower().strip() if parts else ""
        if not name:
            out.append(line)
            continue
        if name in seen:
            removed += 1
        else:
            seen.add(name)
            out.append(line)

    if removed:
        CRM_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")

    return removed
