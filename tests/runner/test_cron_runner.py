import time
import pytest
from unittest.mock import MagicMock
from runner.scheduler.cron_runner import CronRunner


def test_cron_runner_calls_callback_after_interval():
    callback = MagicMock()
    runner = CronRunner(interval_seconds=0.05, callback=callback)
    runner.start()
    time.sleep(0.18)
    runner.stop()
    assert callback.call_count >= 2


def test_cron_runner_stops_cleanly():
    callback = MagicMock()
    runner = CronRunner(interval_seconds=0.05, callback=callback)
    runner.start()
    time.sleep(0.08)
    runner.stop()
    count_at_stop = callback.call_count
    time.sleep(0.15)
    # Should not have called again after stop
    assert callback.call_count == count_at_stop


def test_cron_runner_logs_callback_exceptions_without_crashing():
    def bad_callback():
        raise RuntimeError("simulated failure")

    runner = CronRunner(interval_seconds=0.05, callback=bad_callback)
    runner.start()
    time.sleep(0.15)
    runner.stop()
    # Should not raise — runner survives callback errors
