#!/usr/bin/env python3
"""P4 nightly opportunity learning loop.
Finds high-scored-but-poorly-demoed opportunities (score-vs-demo divergence),
writes a learnings note, and tunes agents/opportunity_worker.md via Gemini.
Runs via the daily learning hook in run_cycle.
"""
import logging
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
LEDGER_FILE = ROOT / "vault" / "opportunities" / "ledger.md"
LEARNINGS_DIR = ROOT / "vault" / "learnings"
PROMPT_FILE = ROOT / "agents" / "opportunity_worker.md"


def _rows() -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    out = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| slug") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 9:
            out.append({"slug": cells[0], "composite": cells[1], "poc": cells[3]})
    return out


def find_divergence(threshold: float = 75) -> list[dict]:
    diverging = []
    for r in _rows():
        try:
            score = float(r["composite"])
        except ValueError:
            continue
        if score >= threshold and r["poc"] in ("weak", "dead"):
            diverging.append(r)
    return diverging


def write_learnings(diverging: list[dict]) -> Path:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out = LEARNINGS_DIR / f"{today}-opportunities.md"
    lines = [f"# Opportunity Learnings — {today}", ""]
    if diverging:
        lines.append("## Score-vs-demo divergence (scored high, demoed poorly)")
        for r in diverging:
            lines.append(f"- [[{r['slug']}]] — composite {r['composite']} but PoC {r['poc']}")
        lines.append("")
        lines.append("These patterns are over-scored. The scout should weight them down next run.")
    else:
        lines.append("_No divergence today — scoring and demos aligned._")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _tune_prompt(diverging: list[dict]) -> None:
    if not diverging or not os.environ.get("GOOGLE_AI_API_KEY"):
        return
    current = PROMPT_FILE.read_text(encoding="utf-8")
    divergence_text = "\n".join(f"- {r['slug']}: scored {r['composite']}, demoed {r['poc']}" for r in diverging)
    client = OpenAI(
        api_key=os.environ["GOOGLE_AI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    try:
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            max_tokens=4096,
            messages=[
                {"role": "system", "content": (
                    "You tune the Prospector scout's prompt. Given ideas that scored high but demoed poorly, "
                    "add or refine 1-3 concrete scoring cautions so the scout stops over-scoring similar ideas. "
                    "Output the FULL revised markdown file, preserving all existing sections. Do not remove workflows."
                )},
                {"role": "user", "content": f"Diverging ideas:\n{divergence_text}\n\nCurrent prompt:\n{current}"},
            ],
        )
        new = resp.choices[0].message.content or ""
        if new.strip() and "Scout workflow" in new:
            PROMPT_FILE.write_text(new, encoding="utf-8")
            log.info("Tuned opportunity_worker.md from %d diverging ideas", len(diverging))
    except Exception as exc:
        log.error("Prompt tune failed: %s", exc)


def run() -> None:
    diverging = find_divergence(75)
    write_learnings(diverging)
    _tune_prompt(diverging)
    log.info("Opportunity synthesis complete — %d diverging ideas", len(diverging))


if __name__ == "__main__":
    run()
