"""
One-time setup: registers 4 scheduled tasks in Windows Task Scheduler.
Run once as administrator: python -m runner.scheduler.setup_windows
"""
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable
RUNNER_SCRIPT = str(Path(__file__).parent.parent.parent / "scripts" / "run_cycle.py")

SCHEDULES = [
    {
        "name": "AIops_DailyHealthCheck",
        "schedule": "/SC DAILY /ST 09:00",
        "description": "Atlas daily health check — 9am",
    },
    {
        "name": "AIops_HourlyQueueScan",
        "schedule": "/SC HOURLY /MO 1",
        "description": "Scout hourly queue scan",
    },
    {
        "name": "AIops_NightlyReport",
        "schedule": "/SC DAILY /ST 22:00",
        "description": "Ledger nightly report — 10pm",
    },
    {
        "name": "AIops_WeeklyEvaluation",
        "schedule": "/SC WEEKLY /D FRI /ST 15:00",
        "description": "Atlas weekly model evaluation — Friday 3pm",
    },
]


def register_task(name: str, schedule: str, description: str) -> bool:
    cmd = (
        f'schtasks /Create /TN "{name}" /TR "{PYTHON} {RUNNER_SCRIPT}" '
        f'{schedule} /F /RL HIGHEST /RU SYSTEM'
    )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  [OK] {name} — {description}")
        return True
    else:
        print(f"  [FAIL] {name}: {result.stderr.strip()}")
        return False


def setup_all() -> None:
    print("Registering AI Ops scheduled tasks in Windows Task Scheduler...")
    for s in SCHEDULES:
        register_task(s["name"], s["schedule"], s["description"])
    print("Done. View tasks with: schtasks /Query /FO LIST /TN AIops*")


if __name__ == "__main__":
    setup_all()
