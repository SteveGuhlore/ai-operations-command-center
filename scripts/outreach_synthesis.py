#!/usr/bin/env python3
"""Pitch (outreach) self-learning loop.

Learns from Pitch's OWN CRM track record and writes a bounded calibration back
into agents/outreach_worker.md, confined to the delimited <!-- AUTO-CALIBRATION -->
block so a run can never rewrite the whole persona (same safety contract as
scripts/opportunity_synthesis.py).

Signals it learns from vault/outreach/crm.md:
  - MISTAKE: over-reliance on `call_queued`. When most rows are parked at
    call_queued, Pitch is defaulting to "phone only" instead of actually sending
    the email / IG DM it found — the documented #1 failure mode in this pod.
  - CHANNEL MIX: which channel Pitch leans on, to surface imbalance.
  - SUCCESS: city+category segments that produced a real reply/close, and any
    pod that booked REAL logged revenue (revenue ledger).

Deterministic — no model call — so it is safe to run nightly and fully testable.
Invoked by the daily learning hook in runner.main._maybe_run_learning.
"""

import logging
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CRM_FILE = ROOT / "vault" / "outreach" / "crm.md"
LEARNINGS_DIR = ROOT / "vault" / "learnings"
PROMPT_FILE = ROOT / "agents" / "outreach_worker.md"
OUTREACH_POD = "local_outreach_pod"

_CAL_RE = re.compile(
    r"(<!-- AUTO-CALIBRATION:START -->)(.*?)(<!-- AUTO-CALIBRATION:END -->)", re.DOTALL
)

# A contact was actually attempted through a real channel.
_SENT = {"emailed", "email_sent", "dm_sent", "dm_queued", "followed_up", "cold_export"}
# A real human signalled back.
_POSITIVE = {"replied", "closed", "booked"}
# Parked without a real send.
_PASSIVE = {"call_queued", "new"}


def _rows() -> list[dict]:
    if not CRM_FILE.exists():
        return []
    out = []
    for line in CRM_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if (
            not line.startswith("|")
            or line.startswith("| Business")
            or set(line) <= set("|- ")
        ):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 8:
            out.append(
                {
                    "business": cells[0],
                    "type": cells[1].lower(),
                    "city": cells[2],
                    "contact": cells[3],
                    "channel": cells[4].lower(),
                    "status": cells[5].lower(),
                }
            )
    return out


def _norm_channel(c: str) -> str:
    c = (c or "").lower()
    if "email" in c:
        return "email"
    if "insta" in c or "dm" in c or "ig" in c:
        return "instagram"
    if "phone" in c or "call" in c:
        return "phone"
    return c or "unknown"


def find_call_queued_overreliance(
    rows: list[dict], min_rows: int = 10, frac: float = 0.5
) -> dict:
    """MISTAKE signal: too many prospects parked at call_queued instead of sent."""
    if not rows:
        return {"triggered": False, "total": 0, "call_queued": 0, "rate": 0.0}
    cq = sum(1 for r in rows if r["status"] == "call_queued")
    rate = cq / len(rows)
    return {
        "triggered": len(rows) >= min_rows and rate >= frac,
        "total": len(rows),
        "call_queued": cq,
        "rate": round(rate, 3),
    }


def channel_mix(rows: list[dict]) -> dict:
    return dict(Counter(_norm_channel(r["channel"]) for r in rows))


def find_segment_winners(rows: list[dict]) -> list[str]:
    """SUCCESS signal: city+category combos that produced a real reply/close."""
    seen = []
    for r in rows:
        if r["status"] in _POSITIVE:
            seg = f"{r['type']} in {r['city']}"
            if seg not in seen:
                seen.append(seg)
    return seen


def find_revenue() -> float:
    try:
        from runner.ledger.revenue import get_pod_revenue

        return round(get_pod_revenue(OUTREACH_POD), 2)
    except Exception:
        return 0.0


def write_learnings(over: dict, mix: dict, winners: list[str], revenue: float) -> Path:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out = LEARNINGS_DIR / f"{today}-outreach.md"
    lines = [f"# Outreach Learnings — {today}", ""]
    lines.append(f"- CRM rows analysed: {over['total']}")
    lines.append(f"- call_queued: {over['call_queued']} ({int(over['rate'] * 100)}%)")
    lines.append(f"- channel mix: {mix or '—'}")
    lines.append(
        f"- segments that replied/closed: {', '.join(winners) if winners else 'none yet'}"
    )
    lines.append(f"- {OUTREACH_POD} real revenue: ${revenue}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def build_calibration(over: dict, mix: dict, winners: list[str], revenue: float) -> str:
    """Compose the directive text for the AUTO-CALIBRATION block. Deterministic."""
    parts = []
    if over.get("triggered"):
        parts.append(
            f"**Stop defaulting to `call_queued`.** {over['call_queued']} of your last "
            f"{over['total']} CRM rows ({int(over['rate'] * 100)}%) are parked at call_queued — "
            f"that is the documented #1 failure: you found a business but did not send the email "
            f"or IG DM that was available. When `structured.emails` or `structured.instagram_handles` "
            f"has a plausible match, SEND IT and set status email_sent / dm_queued. call_queued is "
            f"only valid when you truly have nothing but a phone number."
        )
    if mix:
        dominant = max(mix, key=mix.get)
        if len(mix) == 1 and over.get("total", 0) >= 10:
            parts.append(
                f"**You are using only one channel ({dominant}).** Diversify — try the other "
                f"channel where the contact data supports it, so a single channel's deliverability "
                f"problems don't stall the whole pipeline."
            )
    if winners:
        parts.append(
            f"**Double down on what actually replied:** {', '.join(winners)}. Prioritise these "
            f"city+category segments — a real reply beats raw volume."
        )
    if revenue and revenue > 0:
        parts.append(
            f"**This pod has booked ${revenue} in REAL revenue.** Reinforce the business types and "
            f"channels behind those closes; real cash is the only score that matters."
        )
    if not parts:
        return "_No calibration learned yet._"
    return "\n\n".join(parts)


def update_calibration_block(text: str) -> bool:
    """Replace ONLY the content between the AUTO-CALIBRATION markers. Returns False
    if the file or markers are missing (never rewrites the whole prompt)."""
    if not PROMPT_FILE.exists():
        return False
    cur = PROMPT_FILE.read_text(encoding="utf-8")
    if not _CAL_RE.search(cur):
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    note = (
        f"<!-- Auto-maintained by scripts/outreach_synthesis.py from the Pitch CRM "
        f"track record — do not edit by hand. Updated {today}. -->"
    )

    def _repl(m: "re.Match") -> str:
        return f"{m.group(1)}\n{note}\n{text}\n{m.group(3)}"

    PROMPT_FILE.write_text(_CAL_RE.sub(_repl, cur), encoding="utf-8")
    return True


def run() -> None:
    rows = _rows()
    over = find_call_queued_overreliance(rows)
    mix = channel_mix(rows)
    winners = find_segment_winners(rows)
    revenue = find_revenue()
    write_learnings(over, mix, winners, revenue)
    updated = update_calibration_block(build_calibration(over, mix, winners, revenue))
    log.info(
        "Outreach synthesis: rows=%d call_queued_overreliance=%s channels=%s winners=%d "
        "revenue=%s calibration_updated=%s",
        over["total"],
        over["triggered"],
        mix,
        len(winners),
        revenue,
        updated,
    )


if __name__ == "__main__":
    run()
