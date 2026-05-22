"""Start the dashboard server. Run: python scripts/start_dashboard.py"""
import subprocess
import sys

subprocess.run([
    sys.executable, "-m", "uvicorn",
    "dashboard.server:app",
    "--host", "127.0.0.1",
    "--port", "8765",
    "--reload",
])
