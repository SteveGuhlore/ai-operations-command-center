"""
Recover lost CRM rows from dm-queue.md.

Reads vault/outreach/dm-queue.md, finds business names that aren't already in
vault/outreach/crm.md, and APPENDS them to the CRM as `dm_queued` rows.

Append-only — never overwrites existing CRM content.
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
CRM = ROOT / "vault" / "outreach" / "crm.md"
QUEUE = ROOT / "vault" / "outreach" / "dm-queue.md"


def parse_pipe_row(line: str) -> list[str] | None:
    if not line.strip().startswith("|"):
        return None
    if "Business" in line or line.strip().startswith("|---"):
        return None
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    return parts if len(parts) >= 3 else None


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main() -> None:
    if not CRM.exists() or not QUEUE.exists():
        print("Missing CRM or dm-queue.")
        return

    crm_text = CRM.read_text(encoding="utf-8")
    existing_names = set()
    for line in crm_text.splitlines():
        row = parse_pipe_row(line)
        if row:
            existing_names.add(norm(row[0]))

    print(f"CRM existing rows: {len(existing_names)}")

    queue_text = QUEUE.read_text(encoding="utf-8")
    new_rows: list[str] = []
    skipped = 0
    queue_total = 0

    for line in queue_text.splitlines():
        row = parse_pipe_row(line)
        if not row or len(row) < 4:
            continue
        queue_total += 1
        business, handle, city, *rest = row
        date = rest[-1] if rest else ""

        if norm(business) in existing_names:
            skipped += 1
            continue

        handle = handle if handle.startswith("@") else f"@{handle.lstrip('@')}"
        city_field = city if "," in city else f"{city}, MA"
        new_line = f"| {business} | unknown | {city_field} | {handle} | instagram | dm_queued | {date} | recovered from dm-queue |"
        new_rows.append(new_line)
        existing_names.add(norm(business))

    print(f"dm-queue total rows: {queue_total}")
    print(f"Already in CRM (skipped): {skipped}")
    print(f"New rows to append: {len(new_rows)}")

    if not new_rows:
        return

    sep = "" if crm_text.endswith("\n") else "\n"
    appended = sep + "\n".join(new_rows) + "\n"

    with CRM.open("a", encoding="utf-8") as fh:
        fh.write(appended)

    print(f"Appended {len(new_rows)} rows to {CRM}")


if __name__ == "__main__":
    main()
