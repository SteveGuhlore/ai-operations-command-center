import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class StateFileWatcher:
    def __init__(self, state_file: Path, callback: Callable[[dict], Awaitable[None]]):
        self._file = state_file
        self._callback = callback
        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def read_current(self) -> dict:
        if not self._file.exists():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        handler = _ChangeHandler(self._file, self._callback, self._loop)
        self._observer = Observer()
        self._observer.schedule(handler, str(self._file.parent), recursive=False)
        self._observer.start()

    async def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, state_file: Path, callback, loop):
        self._file = state_file
        self._callback = callback
        self._loop = loop

    def on_modified(self, event):
        if Path(event.src_path).resolve() == self._file.resolve():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # A partial/mid-write read parse-fails; skip this event and keep the
                # last good broadcast rather than wiping the dashboard to {}.
                return
            asyncio.run_coroutine_threadsafe(self._callback(data), self._loop)
