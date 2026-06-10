"""Pre-open paper reset (weekday ~9:25 AM ET, run by a Windows Scheduled Task).

Cancels UNFILLED entry orders, clears the executed-log, and empties the verdicts file so each
market day — and any overnight test/fake data — starts on a clean book. PAPER ONLY: it never
closes filled positions NOR cancels their protective stop/target legs (those guard overnight
holds). Use --dry-run to preview.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")  # explicit path so the scheduled task's cwd doesn't matter

from runner.ledger import alpaca_paper as ap


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-open paper-book reset.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would clear, change nothing.")
    args = parser.parse_args()

    if args.dry_run:
        v = ap._load(ap.VERDICTS_FILE)
        e = ap._load(ap.EXECUTED_LOG)
        print(f"[dry-run] would cancel unfilled entry orders (keeping protective stop/target legs), "
              f"clear {len(e)} executed key(s), empty {len(v)} verdict(s) from {ap.VERDICTS_FILE.name}, "
              f"and queue a pre-open deep-dive task")
        return

    # Shared routine (also used by the runner backstop) so the two can never diverge: flush the
    # session, re-check the research queue against fresh prices, queue the pre-open deep-dive, and
    # mark the day done.
    from runner.ledger.preopen import run_preopen_reset
    summary = run_preopen_reset()
    print("preopen_reset:", summary.get("flush"))
    rc = summary.get("recheck", {})
    if "error" in rc:
        print(f"preopen_reset: research-queue re-check skipped: {rc['error']}")
    else:
        print(f"preopen_reset: research-queue re-check — {rc.get('validated', 0)} validated, "
              f"{rc.get('discarded', 0)} discarded")
    print(f"preopen_reset: pre-open deep-dive {summary.get('deepdive')}")


if __name__ == "__main__":
    main()
