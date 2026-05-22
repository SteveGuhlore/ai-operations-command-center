"""Entry point for scheduled runner invocations."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from runner.main import run_cycle
run_cycle()
