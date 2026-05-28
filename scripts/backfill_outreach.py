"""
Backfill outreach: re-run web_search on every `call_queued` CRM row, send
DM/email for ones with a plausible IG handle or email match, update the row.

Usage:
    python scripts/backfill_outreach.py            # dry-run (no sends, no writes)
    python scripts/backfill_outreach.py --live     # actually send + update CRM
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from runner.tools.web import web_search
from runner.tools.social_dm import send_instagram_dm
from runner.tools.email_sender import send_email

CRM_PATH = Path(__file__).parent.parent / "vault" / "outreach" / "crm.md"
LIVE = "--live" in sys.argv

STOPWORDS = {
    "the", "and", "of", "a", "for", "to", "in", "on", "at", "by", "co",
    "llc", "inc", "ltd", "corp", "company", "services", "service", "shop",
    "store", "studio", "center", "centre", "ma", "salon", "spa",
    "tailor", "tailors", "tailoring", "cleaner", "cleaners", "cleaning",
    "tattoo", "ink", "fitness", "daycare", "care", "handy", "handyman",
    "photography", "photo", "photos", "beauty", "food", "truck", "supply",
    "outlet", "pet", "pets", "dental", "auto", "automotive", "hvac",
    "plumbing", "roofing", "lawn", "electric", "electrical", "dry", "hour",
    "group", "professional", "pro", "llp", "associates", "boutique",
    "construction", "landscaping", "massage", "reflexology", "threading",
    "health", "house", "home", "hair", "nail", "wash", "repair", "movers",
    "moving", "laundromat", "laundry", "barbershop", "barber", "kennel",
    "kennels", "boarding", "art", "arts", "tutoring", "tutor", "yoga",
    "studio", "studios", "video", "videos", "florist", "florists", "deli",
    "bakery", "bakeries", "cafe", "cafes", "catering",
}

NON_US_TLDS = (".co.uk", ".org.uk", ".uk", ".ca", ".com.au", ".au",
               ".de", ".fr", ".eu", ".ie", ".in", ".nz", ".za", ".jp",
               ".cn", ".kr", ".br", ".mx", ".it", ".es", ".nl")

INSTITUTIONAL_TLDS = (".gov", ".edu", ".mil", ".ny.us", ".tx.us", ".ca.us",
                      ".fl.us", ".ga.us", ".il.us", ".oh.us", ".pa.us")

# Wrong-region markers in email local-part or domain (we target MA + neighbors)
WRONG_REGION_TOKENS = (
    "texas", "california", "florida", "chicago", "denver", "phoenix",
    "atlanta", "houston", "dallas", "seattle", "vegas", "miami",
    "syracuse", "minnesota", "minneapolis", "wisconsin", "ohio",
    "arizona", "oregon", "virginia", "kentucky", "tennessee",
)

# Big-chain / mass-corporate domains that almost certainly aren't the local biz
CORP_DOMAINS = (
    "staples.com", "walmart.com", "target.com", "amazon.com",
    "homedepot.com", "lowes.com", "bestbuy.com", "macys.com",
    "comcast.net", "verizon.com", "att.com", "instagram.com",
    "facebook.com", "youtube.com", "linkedin.com",
)

# Country markers that indicate a foreign handle
FOREIGN_HANDLE_MARKERS = (
    "_uk", "_india", "_au", "_aus", "_nz", "_canada", "_jp",
    "uksales", "indiaoffice",
)


def name_tokens(name: str) -> list[str]:
    """Distinctive tokens from the business name (≥4 chars, not generic)."""
    words = re.findall(r"[A-Za-z]+", name.lower())
    return [w for w in words if len(w) >= 4 and w not in STOPWORDS]


def email_plausible(email: str, name: str, city: str) -> bool:
    e = email.lower().strip()
    if any(e.endswith(tld) for tld in NON_US_TLDS):
        return False
    if any(e.endswith(tld) for tld in INSTITUTIONAL_TLDS):
        return False
    domain = e.split("@", 1)[-1] if "@" in e else ""
    if domain in CORP_DOMAINS:
        return False
    if any(marker in e for marker in WRONG_REGION_TOKENS):
        return False
    tokens = name_tokens(name)
    if not tokens:
        return False
    return any(t in e for t in tokens)


def handle_plausible(handle: str, name: str, city: str, sources: list[str]) -> bool:
    h_raw = handle.lstrip("@").lower()
    if any(marker in h_raw for marker in FOREIGN_HANDLE_MARKERS):
        return False
    h = h_raw.replace(".", "").replace("_", "")
    tokens = name_tokens(name)
    if not tokens:
        return False
    if any(t in h for t in tokens):
        return True
    city_tok = city.lower().replace(" ", "")
    if city_tok and city_tok in h and any(t in h for t in tokens):
        return True
    for src in sources:
        src_low = src.lower()
        if f"instagram.com/{h_raw}" in src_low:
            if any(t in src_low for t in tokens):
                return True
    return False


EMAIL_TEMPLATE = """Hi {name},

Noticed you don't have a website yet — you're losing customers who search online before they decide where to go.

We build professional sites for local {type} starting at $299, live in 24 hours. You own it, no monthly fees.

Happy to send some examples if you're curious.

— Stephen
easysimplesites.org

---
Reply STOP and I won't reach out again.
"""

DM_TEMPLATE = (
    "Hey {name}! Noticed you don't have a website — you're losing customers "
    "who search before they visit. We build professional sites starting at "
    "$299, live in 24 hrs. Want to see examples? — Stephen, easysimplesites.org"
)


def parse_row(line: str) -> dict | None:
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 9:
        return None
    fields = parts[1:9]
    if len(fields) != 8:
        return None
    return {
        "business": fields[0],
        "type":     fields[1],
        "location": fields[2],
        "contact":  fields[3],
        "channel":  fields[4],
        "status":   fields[5],
        "date":     fields[6],
        "notes":    fields[7],
        "raw":      line,
    }


def city_from_location(loc: str) -> str:
    return loc.split(",")[0].strip()


def build_new_row(row: dict, new_contact: str, new_channel: str, new_status: str, new_notes: str) -> str:
    return f"| {row['business']} | {row['type']} | {row['location']} | {new_contact} | {new_channel} | {new_status} | {row['date']} | {new_notes} |"


def main() -> None:
    text = CRM_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=False)

    candidates: list[tuple[int, dict]] = []
    for idx, line in enumerate(lines):
        if "call_queued" not in line:
            continue
        row = parse_row(line)
        if not row:
            continue
        if row["status"] != "call_queued":
            continue
        candidates.append((idx, row))

    print(f"Mode: {'LIVE — will send + update CRM' if LIVE else 'DRY-RUN — no sends, no writes'}")
    print(f"Found {len(candidates)} call_queued rows to re-check.\n")

    planned_email: list[tuple[int, dict, str]] = []
    planned_dm:    list[tuple[int, dict, str]] = []
    no_match = 0

    for i, (idx, row) in enumerate(candidates, 1):
        name = row["business"]
        city = city_from_location(row["location"])
        query = f"{name} {city} contact email OR instagram"
        try:
            r = web_search(query)
        except Exception as exc:
            print(f"[{i}/{len(candidates)}] {name[:40]:<40} ERROR: {exc}")
            continue

        s = r.get("structured") or {}
        sources = r.get("sources") or []
        emails = s.get("emails") or []
        igs    = s.get("instagram_handles") or []

        matched_email = next((e for e in emails if email_plausible(e, name, city)), None)
        matched_ig    = next((h for h in igs if handle_plausible(h, name, city, sources)), None)

        if matched_email:
            planned_email.append((idx, row, matched_email))
            print(f"[{i}/{len(candidates)}] EMAIL  {name[:36]:<36}  ->  {matched_email}")
        elif matched_ig:
            planned_dm.append((idx, row, matched_ig))
            print(f"[{i}/{len(candidates)}] DM     {name[:36]:<36}  ->  {matched_ig}")
        else:
            no_match += 1
            if emails or igs:
                preview = (emails + igs)[:2]
                print(f"[{i}/{len(candidates)}] skip   {name[:36]:<36}  ({', '.join(preview)} — no plausible match)")

        time.sleep(0.15)

    print()
    print("=" * 60)
    print(f"PLAN: {len(planned_email)} emails, {len(planned_dm)} DMs, {no_match} unchanged")
    print("=" * 60)

    if not LIVE:
        print("\nDry-run complete. Re-run with --live to actually send + update CRM.")
        return

    print("\nSENDING...")
    updates: dict[int, str] = {}
    sent_email = 0
    sent_dm = 0

    for idx, row, email in planned_email:
        subject = f"{row['business']} — quick question"
        body = EMAIL_TEMPLATE.format(name=row["business"], type=row["type"])
        result = send_email(to_email=email, to_name=row["business"], subject=subject, body=body)
        if result.get("success") or result.get("queued"):
            sent_email += 1
            note = "backfill: sent" if result.get("success") else f"backfill: {result.get('reason', 'queued')}"
            updates[idx] = build_new_row(row, email, "email", "email_sent", note)
            print(f"  EMAIL ok  -> {email}")
        else:
            print(f"  EMAIL FAIL -> {email}: {result.get('error', 'unknown')}")

    for idx, row, handle in planned_dm:
        msg = DM_TEMPLATE.format(name=row["business"])
        result = send_instagram_dm(
            instagram_handle=handle,
            business_name=row["business"],
            message=msg,
            city=city_from_location(row["location"]),
        )
        if result.get("success") or result.get("queued"):
            sent_dm += 1
            note = "backfill: sent" if result.get("success") else f"backfill: {result.get('reason', 'queued')}"
            updates[idx] = build_new_row(row, handle, "instagram", "dm_queued", note)
            print(f"  DM ok     -> {handle}")
        else:
            print(f"  DM FAIL   -> {handle}: {result.get('error', 'unknown')}")

    if updates:
        for idx, new_line in updates.items():
            lines[idx] = new_line
        CRM_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nCRM updated: {len(updates)} rows rewritten.")

    print(f"\nDONE. Emails sent: {sent_email}, DMs sent: {sent_dm}.")


if __name__ == "__main__":
    main()
