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
import re
import socket
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


def _already_running(port: int = 8765) -> bool:
    """A live dashboard on the port means the full system is already up. Prevents the
    duplicate-process / port-conflict pileup that looks like 'agents didn't start'."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


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


MAX_RESUMES = 3


def cleanup_stale_tasks():
    """Resume orphaned in_progress tasks on startup. A task left in_progress means the
    process died (restart / disconnect / crash) mid-run, so re-queue it to todo/ and the
    runner re-runs it next cycle — interrupted work is no longer silently lost. A bounded
    resume_count in the frontmatter stops a crash-inducing 'poison' task from looping
    forever: after MAX_RESUMES it goes to failed/ for human review. Stale locks are cleared."""
    root = Path(__file__).parent.parent / "workspace"
    in_progress = root / "tasks" / "in_progress"
    todo = root / "tasks" / "todo"
    failed = root / "tasks" / "failed"
    locks = root / "locks"
    todo.mkdir(parents=True, exist_ok=True)
    failed.mkdir(parents=True, exist_ok=True)
    resumed = dead = 0
    for f in in_progress.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^resume_count:\s*(\d+)", text, re.MULTILINE)
        count = int(m.group(1)) if m else 0
        if count >= MAX_RESUMES:
            f.rename(failed / f.name)
            dead += 1
            continue
        if m:
            text = re.sub(r"^resume_count:\s*\d+", f"resume_count: {count + 1}",
                          text, count=1, flags=re.MULTILINE)
        else:
            text = re.sub(r"^(status:.*)$", r"\1\nresume_count: 1",
                          text, count=1, flags=re.MULTILINE)
        text = re.sub(r"^status:\s*\w+", "status: todo", text, count=1, flags=re.MULTILINE)
        (todo / f.name).write_text(text, encoding="utf-8")
        f.unlink()
        resumed += 1
    for f in locks.glob("*.lock"):
        f.unlink(missing_ok=True)
    if resumed or dead:
        print(f"Startup recovery: re-queued {resumed} interrupted task(s) to todo/, "
              f"{dead} exceeded retry cap -> failed/. Cleared locks.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=120, help="Seconds between cycles (default: 120 = 2 min)")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("  AI OPS COMMAND CENTER — LAUNCH")
    print("="*50 + "\n")

    if _already_running():
        print("System already running (dashboard live on 8765) — not starting a duplicate.")
        print(f"View at {DASHBOARD_URL}")
        return

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
