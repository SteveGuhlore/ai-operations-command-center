"""
Dev-mode cron runner. Runs the callback on a fixed interval in a background thread.
Use instead of Windows Task Scheduler during development and testing.

Usage:
    from runner.main import run_cycle
    from runner.scheduler.cron_runner import CronRunner
    import time

    runner = CronRunner(interval_seconds=3600, callback=run_cycle)
    runner.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        runner.stop()
"""
import logging
import threading
from typing import Callable

log = logging.getLogger(__name__)


class CronRunner:
    def __init__(self, interval_seconds: float, callback: Callable[[], None]):
        self._interval = interval_seconds
        self._callback = callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._interval + 1)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._interval)
            if self._stop_event.is_set():
                break
            try:
                self._callback()
            except Exception as exc:
                log.error("CronRunner callback error: %s", exc)
