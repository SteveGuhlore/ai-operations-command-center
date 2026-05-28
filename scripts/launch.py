"""
Full system launch. Starts dashboard + cron runner.

Usage:
    python scripts/launch.py                    # Runs every hour (default)
    python scripts/launch.py --interval 1800    # Runs every 30 minutes
    python scripts/launch.py --once             # Run one cycle and exit

Open http://127.0.0.1:8765 to see the live dashboard.
Press Ctrl-C to stop everything.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

REQUIRED_KEYS = ["GOOGLE_AI_API_KEY"]
OPTIONAL_KEYS = ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ETSY_API_KEY", "ETSY_SHOP_ID"]
DASHBOARD_URL = "http://127.0.0.1:8765"


def check_keys():
    missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
    if missing:
        print(f"\nERROR: Missing required environment variables: {', '.join(missing)}")
        print("Add them to .env in the project root. See config/.env.example for the template.")
        sys.exit(1)

    optional_missing = [k for k in OPTIONAL_KEYS if not os.environ.get(k)]
    if optional_missing:
        print(f"NOTE: Optional keys not set (some tools will be skipped): {', '.join(optional_missing)}")


def start_dashboard():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dashboard.server:app",
         "--host", "127.0.0.1", "--port", "8765"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    print(f"Dashboard running at {DASHBOARD_URL}")
    return proc


def cleanup_stale_tasks():
    """Move orphaned in_progress tasks to failed and clear stale locks on startup."""
    root = Path(__file__).parent.parent / "workspace"
    in_progress = root / "tasks" / "in_progress"
    failed = root / "tasks" / "failed"
    locks = root / "locks"
    failed.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in in_progress.glob("*.md"):
        f.rename(failed / f.name)
        count += 1
    for f in locks.glob("*.lock"):
        f.unlink(missing_ok=True)
    if count:
        print(f"Startup cleanup: moved {count} stale task(s) to failed/, cleared locks.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=120, help="Seconds between cycles (default: 120 = 2 min)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("  AI OPS COMMAND CENTER — LAUNCH")
    print("="*50 + "\n")

    check_keys()
    cleanup_stale_tasks()

    dashboard_proc = start_dashboard()

    from runner.main import run_cycle

    if args.once:
        print("Running one cycle...\n")
        run_cycle()
        print("\nCycle complete. Dashboard still running.")
        print(f"View at {DASHBOARD_URL}")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            dashboard_proc.terminate()
            print("\nStopped.")
        return

    from runner.scheduler.cron_runner import CronRunner

    print(f"Starting cron runner — cycle every {args.interval}s")
    print(f"Dashboard: {DASHBOARD_URL}")
    print("Press Ctrl-C to stop.\n")

    cron = CronRunner(interval_seconds=args.interval, callback=run_cycle)
    cron.start()

    run_cycle()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
        cron.stop()
        dashboard_proc.terminate()
        print("Stopped.")


if __name__ == "__main__":
    main()
