"""Backfill vault/outreach/crm.md from historical outreach task-output prose.

The outreach_worker narrated the prospects it found/contacted in each done task's "## Agent
Output" but never persisted them to the CRM (the file was empty). This one-time script
reconstructs the CRM from that prose. It handles the two formats the agent used across its run
history:

  Format A (most common, richest):
    *   **Business Name**: Found email `x@y.com`. Sent email. Status: `email_sent`.
    *   **Business Name**: Found Instagram handle `@handle`. ... Status: `dm_queued`.
    *   **Business Name**: Only found phone number `(508) 587-5700`. Status: `call_queued`.
    (city comes from a "Business Name (City, MA)" bullet earlier in the same output; the
     actual email/handle/phone IS recovered here)

  Format B (early runs):
    - **Salem, MA (Hair Salons)**: ... For "Texture Salon", an email was found and sent. ...
    (quoted names under a city/category header; status inferred from surrounding words; no contact)

Deduped by business name across all tasks (earliest contact kept). Output matches the parser
in dashboard/server.py exactly.

Usage:
    python scripts/backfill_crm_from_tasks.py            # dry-run: parse + report, no write
    python scripts/backfill_crm_from_tasks.py --write    # write vault/outreach/crm.md
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
DONE_DIR = ROOT / "workspace" / "tasks" / "done"
CRM_FILE = Path(os.environ.get("OUTREACH_CRM_FILE", str(ROOT / "vault" / "outreach" / "crm.md")))

HEADER = "| Business | Type | City | Contact | Channel | Status | Date | Notes |"
DIVIDER = "|----------|------|------|---------|---------|--------|------|-------|"

WRITE = "--write" in sys.argv

_AGENT = re.compile(r"assigned_agent:\s*outreach_worker")
_CREATED = re.compile(r"created_at:\s*(\d{8})")

_STATUS = "email_sent|dm_queued|call_queued|emailed|dm_sent|replied|closed|no_interest|followed_up"
_STATUS_ALIAS = {"emailed": "email_sent", "dm_sent": "dm_queued"}

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HANDLE = re.compile(r"@[A-Za-z0-9_.]{2,30}")
_PHONE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_CITY = re.compile(r"\(([^)]*?,\s*[A-Z]{2})\)")

# Format A: a bold business name, then anything ON THE SAME LINE, then an explicit Status: `...`.
# [ \t] (not \s) around the colon so the match can't bridge a newline into the next line's Status
# (which would capture the section header "Attempted Contact & Updated CRM" as a business).
_FMT_A = re.compile(r"\*\*([^*\n]{2,70}?)\*\*[ \t]*:?[ \t]*([^\n]*?Status:\s*`?(" + _STATUS + r")`?)",
                    re.IGNORECASE)
# A "Business Name (City, ST)" bullet — builds the name->city map for Format A.
_BULLET_CITY = re.compile(r"(?m)^\s*[\*\-•]?\s*\**\s*([^*\n(]{2,70}?)\s*\**\s*\(([^)]*?,\s*[A-Z]{2})\)")
# Format B: **City, ST (Category)** header
_FMT_B_HDR = re.compile(r"\*\*\s*([A-Za-z .'-]+?,\s*[A-Z]{2})\s*\(([^)]+)\)\s*\*\*")
_QUOTE = re.compile(r"[\"“]([^\"”]{2,60})[\"”]")

# light category inference from the business name (Format A has no explicit category)
_CAT_HINTS = [
    ("nail", "Nail Salon"), ("barber", "Barbershop"), ("salon", "Salon"), ("spa", "Spa"),
    ("auto", "Auto Repair"), ("tire", "Auto Repair"), ("plumb", "Plumber"),
    ("electric", "Electrician"), ("hvac", "HVAC"), ("roof", "Roofer"), ("paint", "Painter"),
    ("landscap", "Landscaping"), ("lawn", "Lawn Care"), ("greenhouse", "Florist"),
    ("florist", "Florist"), ("flower", "Florist"), ("clean", "Cleaning"), ("cafe", "Cafe"),
    ("coffee", "Cafe"), ("bakery", "Bakery"), ("daycare", "Daycare"), ("tutor", "Tutoring"),
    ("fitness", "Fitness"), ("yoga", "Yoga"), ("tattoo", "Tattoo"), ("massage", "Massage"),
    ("photo", "Photographer"), ("dry clean", "Dry Cleaner"), ("laundr", "Laundromat"),
    ("tailor", "Tailor"), ("moving", "Moving"), ("pet", "Pet Services"), ("groom", "Pet Grooming"),
    ("restaurant", "Restaurant"), ("pizza", "Restaurant"), ("deli", "Deli"), ("heating", "HVAC"),
]

_NOISE = {"website", "interested", "status", "email", "instagram", "note", "failure",
          "metric", "pattern", "crm", "the system", "read_inbox", "find_prospects"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _date(text: str) -> str:
    m = _CREATED.search(text)
    return f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}" if m else ""


def _category(name: str) -> str:
    low = name.lower()
    for hint, cat in _CAT_HINTS:
        if hint in low:
            return cat
    return ""


def _is_business(name: str) -> bool:
    n = name.strip()
    if len(n) < 3 or _norm(n) in {_norm(x) for x in _NOISE}:
        return False
    if n.lower() in _NOISE:
        return False
    return bool(re.search(r"[A-Za-z]", n)) and not n.startswith(("http", "`"))


def _contact_and_channel(detail: str, status: str) -> tuple[str, str]:
    detail_no_email = _EMAIL.sub(" ", detail)
    email = _EMAIL.search(detail)
    handle = _HANDLE.search(detail_no_email)
    phone = _PHONE.search(detail_no_email)
    if status == "email_sent" and email:
        return email.group(0), "email"
    if status == "dm_queued" and handle:
        return handle.group(0), "instagram"
    if status == "call_queued" and phone:
        return phone.group(0), "phone"
    if email:
        return email.group(0), "email"
    if handle:
        return handle.group(0), "instagram"
    if phone:
        return phone.group(0), "phone"
    return "—", {"email_sent": "email", "dm_queued": "instagram", "call_queued": "phone"}.get(status, "")


def _classify_b(window: str) -> tuple[str, str]:
    w = window.lower()
    if re.search(r"no plausible|no .{0,20}(email|instagram)|call[_ ]queued|phone[- ]only|marked .{0,12}call", w):
        return "phone", "call_queued"
    if re.search(r"instagram|ig dm|\bdm\b", w) and re.search(r"queu|sent", w):
        return "instagram", "dm_queued"
    if "email" in w and re.search(r"sent|found", w):
        return "email", "email_sent"
    return "phone", "call_queued"


def parse_task(text: str) -> list[dict]:
    if not _AGENT.search(text):
        return []
    out_idx = text.find("## Agent Output")
    if out_idx == -1:
        return []
    body = text[out_idx:]
    run_date = _date(text)
    rows: dict[str, dict] = {}

    def _add(name, status, channel, contact, city, category):
        name = name.strip().strip(".:*").strip()
        if not _is_business(name):
            return
        key = _norm(name)
        status = _STATUS_ALIAS.get(status, status)
        cur = rows.get(key)
        # prefer the row that actually has a contact
        if cur and (cur["contact"] != "—" or contact == "—"):
            return
        rows[key] = {"business": name, "type": category or _category(name), "city": city,
                     "contact": contact or "—", "channel": channel, "status": status, "date": run_date}

    # name -> city from bullets (for Format A, whose status lines carry no city)
    city_map = {}
    for m in _BULLET_CITY.finditer(body):
        nm = m.group(1).strip().strip("*").strip()
        if _is_business(nm):
            city_map[_norm(nm)] = m.group(2).strip()

    # FORMAT A — explicit Status lines (richest, has real contact)
    for m in _FMT_A.finditer(body):
        name, detail, status = m.group(1), m.group(2), m.group(3).lower()
        status = _STATUS_ALIAS.get(status, status)
        contact, channel = _contact_and_channel(detail, status)
        _add(name, status, channel, contact, city_map.get(_norm(name), ""), "")

    # FORMAT B — quoted names under a **City (Category)** header
    hdrs = list(_FMT_B_HDR.finditer(body))
    for i, hdr in enumerate(hdrs):
        city, category = hdr.group(1).strip(), hdr.group(2).strip()
        seg = body[hdr.end(): hdrs[i + 1].start() if i + 1 < len(hdrs) else len(body)]
        quotes = list(_QUOTE.finditer(seg))
        for j, q in enumerate(quotes):
            nxt = quotes[j + 1].end() if j + 1 < len(quotes) else min(len(seg), q.end() + 200)
            channel, status = _classify_b(seg[q.end():nxt])
            _add(q.group(1), status, channel, "—", city, category)

    return list(rows.values())


def _row(r: dict) -> str:
    note = "backfilled from task history"
    return "| " + " | ".join([
        r["business"], r.get("type", ""), r.get("city", ""), r.get("contact", "—"),
        r.get("channel", ""), r["status"], r.get("date", ""), note,
    ]) + " |"


def main() -> None:
    files = sorted(DONE_DIR.glob("*.md"))  # chronological -> earliest contact kept
    seen: dict[str, dict] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for r in parse_task(text):
            key = _norm(r["business"])
            if not key:
                continue
            if key not in seen:
                seen[key] = r
            elif seen[key]["contact"] == "—" and r["contact"] != "—":
                seen[key]["contact"] = r["contact"]      # upgrade a blank contact if a later run has one
                seen[key]["channel"] = r["channel"]

    rows = list(seen.values())
    by_status, with_contact = {}, 0
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        if r["contact"] != "—":
            with_contact += 1

    print(f"Scanned {len(files)} done tasks -> {len(rows)} unique prospects recovered "
          f"({with_contact} with a real email/handle/phone)")
    for s, n in sorted(by_status.items()):
        print(f"  {s}: {n}")
    print("\nSample:")
    for r in rows[:12]:
        print("  " + _row(r))

    if not WRITE:
        print(f"\n(dry-run — pass --write to persist to {CRM_FILE})")
        return

    CRM_FILE.parent.mkdir(parents=True, exist_ok=True)
    CRM_FILE.write_text("\n".join([HEADER, DIVIDER] + [_row(r) for r in rows]) + "\n", encoding="utf-8")
    print(f"\nWrote {len(rows)} rows to {CRM_FILE}")


if __name__ == "__main__":
    main()
