"""Backfill vault/outreach/crm.md from historical outreach task outputs.

The outreach_worker narrated the prospects it found/contacted in each done task's
"## Agent Output" prose, but never persisted them to the CRM (see the empty
vault/outreach/crm.md). This one-time script reconstructs the CRM from that prose
so the dashboard, synthesis, and revenue rollup have the historical record.

What it can recover from the prose: business name, city, category, channel/status,
and the run date. What it usually CANNOT recover: the exact contact email/handle
(left blank). It is therefore an approximate reconstruction, not a perfect mirror —
but it is the real outreach history, deduped by business name.

Usage:
    python scripts/backfill_crm_from_tasks.py            # dry-run: parse + report, no write
    python scripts/backfill_crm_from_tasks.py --write    # write vault/outreach/crm.md
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DONE_DIR = ROOT / "workspace" / "tasks" / "done"
CRM_FILE = Path(__import__("os").environ.get(
    "OUTREACH_CRM_FILE", str(ROOT / "vault" / "outreach" / "crm.md")))

HEADER = "| Business | Type | City | Contact | Channel | Status | Date | Notes |"
DIVIDER = "|----------|------|------|---------|---------|--------|------|-------|"

WRITE = "--write" in sys.argv

# A segment header in the prose: **Salem, MA (Hair Salons)**:
_SEG = re.compile(r"\*\*\s*([A-Za-z .'-]+?,\s*[A-Z]{2})\s*\(([^)]+)\)\s*\*\*")
_QUOTE = re.compile(r"[\"“]([^\"”]{2,80})[\"”]")
_AGENT = re.compile(r"assigned_agent:\s*outreach_worker")
_CREATED = re.compile(r"created_at:\s*(\d{8})")


def _classify(window: str) -> tuple[str, str]:
    """(channel, status) from the text around a quoted business name."""
    w = window.lower()
    # Negative / phone-only case first — "marked call_queued" and "no plausible email or
    # Instagram" must not be mistaken for an actual email/DM send.
    if re.search(r"no plausible|no .{0,20}(email|instagram)|call[_ ]queued|phone[- ]only|marked .{0,12}call", w):
        return "phone", "call_queued"
    if re.search(r"instagram|ig dm|\bdm\b", w) and re.search(r"queu|sent", w):
        return "instagram", "dm_queued"
    if "email" in w and re.search(r"sent|found", w):
        return "email", "email_sent"
    return "phone", "call_queued"


def _date(text: str) -> str:
    m = _CREATED.search(text)
    if not m:
        return ""
    d = m.group(1)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def parse_task(text: str) -> list[dict]:
    if not _AGENT.search(text):
        return []
    out_idx = text.find("## Agent Output")
    if out_idx == -1:
        return []
    body = text[out_idx:]
    run_date = _date(text)

    rows: list[dict] = []
    # Split body into segments by city/category headers, carrying each header's text.
    matches = list(_SEG.finditer(body))
    for i, seg in enumerate(matches):
        city, category = seg.group(1).strip(), seg.group(2).strip()
        seg_text = body[seg.end(): matches[i + 1].start() if i + 1 < len(matches) else len(body)]
        quotes = list(_QUOTE.finditer(seg_text))
        for j, q in enumerate(quotes):
            name = q.group(1).strip().strip(".,")
            nxt = quotes[j + 1].end() if j + 1 < len(quotes) else min(len(seg_text), q.end() + 200)
            channel, status = _classify(seg_text[q.end():nxt])
            rows.append({
                "business": name, "type": category, "city": city,
                "channel": channel, "status": status, "date": run_date,
            })
    return rows


def _row(r: dict) -> str:
    return "| " + " | ".join([
        r["business"], r["type"], r["city"], "—",
        r["channel"], r["status"], r["date"], "backfilled from task history",
    ]) + " |"


def main() -> None:
    files = sorted(DONE_DIR.glob("*.md"))
    seen: set[str] = set()
    rows: list[dict] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for r in parse_task(text):
            key = r["business"].lower()
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(r)

    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    print(f"Scanned {len(files)} done tasks → {len(rows)} unique prospects recovered")
    for s, n in sorted(by_status.items()):
        print(f"  {s}: {n}")
    print("\nSample:")
    for r in rows[:8]:
        print("  " + _row(r))

    if not WRITE:
        print("\n(dry-run — pass --write to persist to", CRM_FILE, ")")
        return

    CRM_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [HEADER, DIVIDER] + [_row(r) for r in rows]
    CRM_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {len(rows)} rows to {CRM_FILE}")


if __name__ == "__main__":
    main()
