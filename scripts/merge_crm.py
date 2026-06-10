"""Merge two outreach CRM files into a deduped union — used when restoring an older, richer CRM
(e.g. from a pre-VM vault) without losing any leads the running machine added since.

Usage:
    python merge_crm.py OLD.md NEW.md OUT.md

OLD is treated as authoritative for ordering/contacts (it's the fuller history); NEW contributes
any businesses OLD doesn't have. Dedup is by normalized business name; when both have a row, the
one carrying a real contact wins. Output matches dashboard/server.py's parser exactly.
"""
import re
import sys

HEADER = "| Business | Type | City | Contact | Channel | Status | Date | Notes |"
DIVIDER = "|----------|------|------|---------|---------|--------|------|-------|"
_BLANK = {"", "—", "-", "n/a", "none"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _rows(path: str) -> list[list[str]]:
    out = []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return out
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        if cells[0].lower() == "business" or set(cells[0]) <= {"-", ":", " "}:
            continue
        # pad short rows to 8 cells so indexing is safe
        while len(cells) < 8:
            cells.append("")
        out.append(cells[:8])
    return out


def _has_contact(cells: list[str]) -> bool:
    return cells[3].strip().lower() not in _BLANK


def main() -> None:
    old, new, out = sys.argv[1], sys.argv[2], sys.argv[3]
    seen: dict[str, list[str]] = {}
    order: list[str] = []
    added_from_new = 0
    for src in (old, new):
        for cells in _rows(src):
            k = _norm(cells[0])
            if not k:
                continue
            if k not in seen:
                seen[k] = cells
                order.append(k)
                if src == new:
                    added_from_new += 1
            elif not _has_contact(seen[k]) and _has_contact(cells):
                seen[k] = cells  # upgrade a blank-contact row with a real one

    with open(out, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n" + DIVIDER + "\n")
        for k in order:
            f.write("| " + " | ".join(seen[k]) + " |\n")

    print(f"merged {len(_rows(old))} (old) + {len(_rows(new))} (new) "
          f"-> {len(order)} unique businesses (+{added_from_new} the running machine added)")


if __name__ == "__main__":
    main()
