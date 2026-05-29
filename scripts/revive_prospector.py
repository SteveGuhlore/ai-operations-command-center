#!/usr/bin/env python3
"""Operator control for the Prospector runway (doomsday clock).

  python scripts/revive_prospector.py            # show runway status
  python scripts/revive_prospector.py --status   # show runway status
  python scripts/revive_prospector.py --revive    # bring a paused pod back to life
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from runner.ledger.runway import compute_runway, revive


def main() -> int:
    ap = argparse.ArgumentParser(description="Prospector runway control")
    ap.add_argument("--revive", action="store_true", help="reset the clock and reactivate the pod")
    ap.add_argument("--status", action="store_true", help="print current runway state")
    args = ap.parse_args()

    if args.revive:
        state = revive()
        print("Prospector REVIVED — runway reset.")
    else:
        state = compute_runway()

    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
