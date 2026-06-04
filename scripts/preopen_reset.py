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

    print("preopen_reset:", ap.flush_session())

    # Queue a pre-open deep-dive so Tony re-evaluates his book and the watchlist before the open,
    # rather than waiting on the bot's first intraday bridge (which can land late morning).
    from datetime import date
    from runner.bridge import tony_bridge
    tony_bridge.make_preopen_deepdive(str(date.today()))
    print("preopen_reset: queued pre-open deep-dive")


if __name__ == "__main__":
    main()
