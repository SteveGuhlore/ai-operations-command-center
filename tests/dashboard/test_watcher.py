import json
import asyncio
import pytest
from pathlib import Path
from dashboard.watcher import StateFileWatcher


@pytest.mark.asyncio
async def test_watcher_calls_callback_on_file_change(tmp_path):
    state_file = tmp_path / "dashboard-state.json"
    state_file.write_text(json.dumps({"agents": {}, "tasks": {}, "budget": {}}))
    received = []

    async def on_change(data: dict):
        received.append(data)

    watcher = StateFileWatcher(state_file, on_change)
    await watcher.start()
    state_file.write_text(json.dumps({"agents": {"manager": {"state": "idle"}}, "tasks": {}, "budget": {}}))
    await asyncio.sleep(1.5)
    await watcher.stop()
    assert len(received) >= 1
    assert received[-1]["agents"]["manager"]["state"] == "idle"


def test_watcher_reads_initial_state(tmp_path):
    state_file = tmp_path / "dashboard-state.json"
    state_file.write_text(json.dumps({"agents": {}, "tasks": {"todo": 5}, "budget": {}}))
    async def noop(data): pass
    watcher = StateFileWatcher(state_file, noop)
    data = watcher.read_current()
    assert data["tasks"]["todo"] == 5


def test_watcher_returns_empty_dict_when_file_missing(tmp_path):
    state_file = tmp_path / "nonexistent.json"
    async def noop(data): pass
    watcher = StateFileWatcher(state_file, noop)
    assert watcher.read_current() == {}
