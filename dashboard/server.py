import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dashboard.watcher import StateFileWatcher

STATE_FILE = Path(__file__).parent.parent / "workspace" / "dashboard-state.json"

_connections: Set[WebSocket] = set()
_watcher: StateFileWatcher | None = None


def _read_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


async def _broadcast(data: dict) -> None:
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _watcher
    _watcher = StateFileWatcher(STATE_FILE, _broadcast)
    await _watcher.start()
    yield
    if _watcher:
        await _watcher.stop()


app = FastAPI(lifespan=_lifespan)


@app.get("/", response_class=HTMLResponse)
async def root():
    html_file = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/state")
async def get_state():
    return _read_state()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _connections.add(ws)
    try:
        await ws.send_text(json.dumps(_read_state()))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _connections.discard(ws)
