# 2D Dashboard — Implementation Plan 2 of 3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live 2D web dashboard that reads `workspace/dashboard-state.json` and displays all 11 agents, the task pipeline, pod activity, budget meter, and activity log — updating in real time via WebSocket.

**Architecture:** A Python FastAPI server reads the dashboard state file and pushes updates to connected browsers via WebSocket whenever the file changes (using a polling watcher). The frontend is a single `dashboard/index.html` file with vanilla JS — no framework, no build step, instant load. Agent cards show live state with CSS glow animations. The runner (Plan 1) writes `workspace/dashboard-state.json` after each cycle; the dashboard server watches that file.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, websockets, watchdog, vanilla HTML/CSS/JS. No React, no bundler.

**Prerequisite:** Plan 1 must be complete. The runner must be writing `workspace/dashboard-state.json`.

---

## File Map

```
dashboard/
  server.py          # FastAPI app — serves index.html, pushes state via WebSocket
  watcher.py         # watchdog observer that detects state file changes
  index.html         # single-file frontend — agent grid, task queue, log, pod tabs
requirements.txt     # add: fastapi, uvicorn[standard], watchdog
tests/
  dashboard/
    __init__.py
    test_server.py
    test_watcher.py
```

---

## Task 1: Install Dashboard Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dashboard dependencies to `requirements.txt`**

```
anthropic>=0.40.0
pyyaml>=6.0
pytest>=8.0
pytest-mock>=3.12
pytest-asyncio>=0.23
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
watchdog>=4.0.0
httpx>=0.27.0
```

- [ ] **Step 2: Install**

```powershell
pip install -r requirements.txt
```

Expected: Successfully installed fastapi, uvicorn, watchdog, httpx (and deps).

- [ ] **Step 3: Create test directory**

```powershell
New-Item -ItemType Directory -Force tests\dashboard
"" | Out-File tests\dashboard\__init__.py -Encoding utf8
"" | Out-File dashboard\__init__.py -Encoding utf8
```

- [ ] **Step 4: Commit**

```powershell
git add requirements.txt tests\dashboard\__init__.py dashboard\__init__.py
git commit -m "feat: add dashboard dependencies"
```

---

## Task 2: State File Watcher

**Files:**
- Create: `dashboard/watcher.py`
- Create: `tests/dashboard/test_watcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/dashboard/test_watcher.py
import json
import time
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

    # Modify the file
    state_file.write_text(json.dumps({"agents": {"manager": {"state": "idle"}}, "tasks": {}, "budget": {}}))
    await asyncio.sleep(1.5)  # give watcher time to detect change

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
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/dashboard/test_watcher.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `dashboard/watcher.py`**

```python
# dashboard/watcher.py
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
            data = {}
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
            asyncio.run_coroutine_threadsafe(self._callback(data), self._loop)
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/dashboard/test_watcher.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```powershell
git add dashboard\watcher.py tests\dashboard\test_watcher.py
git commit -m "feat: add state file watcher for dashboard"
```

---

## Task 3: Dashboard Server

**Files:**
- Create: `dashboard/server.py`
- Create: `tests/dashboard/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/dashboard/test_server.py
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def state_file(tmp_path):
    f = tmp_path / "dashboard-state.json"
    f.write_text(json.dumps({
        "updated_at": 1700000000.0,
        "agents": {
            "manager": {"state": "idle", "task_id": "", "last_action": "completed TASK-001", "updated_at": 1700000000.0}
        },
        "tasks": {"todo": 3, "in_progress": 1, "review": 0, "done": 10, "failed": 0},
        "budget": {"spent_usd": 2.14, "cap_usd": 50.0},
    }), encoding="utf-8")
    return f


def _make_client(state_file):
    import dashboard.server as server_module
    server_module.STATE_FILE = state_file
    from importlib import reload
    reload(server_module)
    return TestClient(server_module.app)


def test_get_state_returns_json(state_file):
    client = _make_client(state_file)
    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agents"]["manager"]["state"] == "idle"
    assert data["tasks"]["todo"] == 3
    assert data["budget"]["spent_usd"] == pytest.approx(2.14)


def test_get_root_returns_html(state_file):
    client = _make_client(state_file)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_get_state_returns_empty_when_file_missing(tmp_path):
    import dashboard.server as server_module
    server_module.STATE_FILE = tmp_path / "nonexistent.json"
    from importlib import reload
    reload(server_module)
    client = TestClient(server_module.app)
    resp = client.get("/state")
    assert resp.status_code == 200
    assert resp.json() == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/dashboard/test_server.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `dashboard/server.py`**

```python
# dashboard/server.py
import json
import asyncio
from pathlib import Path
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from dashboard.watcher import StateFileWatcher

STATE_FILE = Path(__file__).parent.parent / "workspace" / "dashboard-state.json"

app = FastAPI()
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


@app.on_event("startup")
async def _startup():
    global _watcher
    _watcher = StateFileWatcher(STATE_FILE, _broadcast)
    await _watcher.start()


@app.on_event("shutdown")
async def _shutdown():
    if _watcher:
        await _watcher.stop()


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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/dashboard/test_server.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```powershell
git add dashboard\server.py tests\dashboard\test_server.py
git commit -m "feat: add FastAPI dashboard server with WebSocket and state endpoint"
```

---

## Task 4: Dashboard Frontend

**Files:**
- Create: `dashboard/index.html`

This is a single self-contained HTML file. No tests — verified by opening in browser.

- [ ] **Step 1: Create `dashboard/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Ops Command Center</title>
<style>
  :root {
    --bg: #0a0e1a;
    --panel: #111827;
    --border: #1f2937;
    --text: #e2e8f0;
    --muted: #6b7280;
    --green: #10b981;
    --orange: #f59e0b;
    --red: #ef4444;
    --blue: #3b82f6;
    --purple: #8b5cf6;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; font-size: 13px; height: 100vh; display: flex; flex-direction: column; }

  /* TOPBAR */
  #topbar { background: var(--panel); border-bottom: 1px solid var(--border); padding: 8px 16px; display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
  #topbar h1 { font-size: 14px; letter-spacing: 2px; color: var(--blue); }
  .level-badge { background: #1e3a5f; color: var(--blue); padding: 2px 8px; border-radius: 4px; font-size: 11px; }
  #budget-bar-wrap { margin-left: auto; display: flex; align-items: center; gap: 8px; }
  #budget-label { font-size: 11px; color: var(--muted); }
  #budget-bar { width: 120px; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
  #budget-fill { height: 100%; background: var(--green); border-radius: 3px; transition: width 0.5s, background 0.3s; }
  #budget-text { font-size: 11px; color: var(--text); min-width: 90px; }

  /* MAIN LAYOUT */
  #main { display: grid; grid-template-columns: 180px 1fr 240px; gap: 1px; flex: 1; overflow: hidden; background: var(--border); }
  .panel { background: var(--panel); padding: 12px; overflow-y: auto; }

  /* LEFT PANEL */
  .section-title { font-size: 10px; letter-spacing: 1.5px; color: var(--muted); margin-bottom: 8px; }
  .queue-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 12px; }
  .queue-count { font-weight: bold; }
  .queue-count.todo { color: var(--text); }
  .queue-count.active { color: var(--blue); }
  .queue-count.review { color: var(--orange); }
  .queue-count.done { color: var(--green); }
  .queue-count.failed { color: var(--red); }
  .divider { border: none; border-top: 1px solid var(--border); margin: 10px 0; }
  .pod-item { padding: 4px 6px; cursor: pointer; border-radius: 4px; font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
  .pod-item:hover, .pod-item.active { background: #1f2937; color: var(--text); }
  .pod-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
  .pod-item.active .pod-dot { background: var(--green); }

  /* AGENT GRID */
  #agent-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; align-content: start; }
  .agent-card {
    background: #0d1117;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    cursor: pointer;
    transition: border-color 0.2s;
    position: relative;
    overflow: hidden;
  }
  .agent-card:hover { border-color: #374151; }
  .agent-card.working { border-color: var(--green); box-shadow: 0 0 12px rgba(16,185,129,0.15); }
  .agent-card.error { border-color: var(--red); box-shadow: 0 0 12px rgba(239,68,68,0.15); }
  .agent-card.budget_paused { border-color: var(--orange); box-shadow: 0 0 12px rgba(245,158,11,0.15); }
  .agent-card.offline { border: 1px dashed var(--border); opacity: 0.5; }
  .agent-name { font-size: 11px; color: var(--muted); letter-spacing: 1px; }
  .agent-display { font-size: 14px; font-weight: bold; margin: 4px 0; }
  .agent-state { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
  .agent-state.idle { color: var(--muted); }
  .agent-state.working { color: var(--green); }
  .agent-state.error { color: var(--red); }
  .agent-state.budget_paused { color: var(--orange); }
  .agent-state.offline { color: var(--muted); }
  .agent-task { font-size: 10px; color: var(--muted); margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pulse { animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }

  /* DETAIL PANEL */
  #detail-panel { display: none; }
  #detail-panel.visible { display: block; }
  #detail-title { font-size: 12px; font-weight: bold; margin-bottom: 8px; color: var(--blue); }
  #detail-content { font-size: 11px; color: var(--muted); line-height: 1.6; }
  #detail-log { background: #060a12; border: 1px solid var(--border); border-radius: 4px; padding: 8px; font-size: 10px; max-height: 200px; overflow-y: auto; margin-top: 8px; white-space: pre-wrap; word-break: break-all; }

  /* RIGHT PANEL - ACTIVITY LOG */
  #log-panel .section-title { margin-bottom: 6px; }
  #activity-log { font-size: 10px; line-height: 1.8; }
  .log-entry { display: flex; gap: 8px; padding: 2px 0; border-bottom: 1px solid #0d1117; }
  .log-time { color: var(--muted); flex-shrink: 0; }
  .log-agent { color: var(--blue); flex-shrink: 0; min-width: 60px; }
  .log-msg { color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  #status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); margin-left: auto; }
  #status-dot.connected { background: var(--green); }
</style>
</head>
<body>

<div id="topbar">
  <h1>AI OPS COMMAND CENTER</h1>
  <span class="level-badge" id="level-badge">Level 2</span>
  <div id="budget-bar-wrap">
    <span id="budget-label">BUDGET</span>
    <div id="budget-bar"><div id="budget-fill" style="width:0%"></div></div>
    <span id="budget-text">$0.00 / $50.00</span>
  </div>
  <div id="status-dot" title="WebSocket disconnected"></div>
</div>

<div id="main">

  <!-- LEFT: queue + pods -->
  <div class="panel" id="left-panel">
    <div class="section-title">TASK QUEUE</div>
    <div class="queue-row"><span>todo</span><span class="queue-count todo" id="q-todo">0</span></div>
    <div class="queue-row"><span>active</span><span class="queue-count active" id="q-active">0</span></div>
    <div class="queue-row"><span>review</span><span class="queue-count review" id="q-review">0</span></div>
    <div class="queue-row"><span>done</span><span class="queue-count done" id="q-done">0</span></div>
    <div class="queue-row"><span>failed</span><span class="queue-count failed" id="q-failed">0</span></div>
    <hr class="divider">
    <div class="section-title">REVENUE PODS</div>
    <div id="pod-list"></div>
  </div>

  <!-- CENTER: agent grid + detail -->
  <div class="panel">
    <div id="agent-grid"></div>
    <div id="detail-panel">
      <hr class="divider">
      <div id="detail-title"></div>
      <div id="detail-content"></div>
      <div id="detail-log"></div>
    </div>
  </div>

  <!-- RIGHT: activity log -->
  <div class="panel" id="log-panel">
    <div class="section-title">ACTIVITY LOG</div>
    <div id="activity-log"></div>
  </div>

</div>

<script>
const AGENTS = [
  { role: "manager",                display: "Atlas",       name: "MANAGER" },
  { role: "heavy_worker",           display: "Forge",       name: "HEAVY WORKER" },
  { role: "debug_worker",           display: "Scout",       name: "DEBUG WORKER" },
  { role: "content_worker",         display: "Muse",        name: "CONTENT" },
  { role: "media_worker",           display: "Frame",       name: "MEDIA" },
  { role: "audio_worker",           display: "Echo",        name: "AUDIO" },
  { role: "guard_worker",           display: "Guard",       name: "GUARD" },
  { role: "budget_worker",          display: "Ledger",      name: "BUDGET" },
  { role: "digital_product_worker", display: "Maker",       name: "DIGITAL PROD" },
  { role: "marketing_worker",       display: "Market",      name: "MARKETING" },
  { role: "market_research_worker", display: "Tony Stocks", name: "MARKET RES" },
];

const PODS = [
  "Etsy Store", "Dropshipping", "Affiliate Content",
  "Short-Form Video", "Digital Products", "Lead Gen",
  "Stock Research", "App SaaS",
];

let selectedAgent = null;
let logEntries = [];

// Build agent grid
const grid = document.getElementById("agent-grid");
AGENTS.forEach(a => {
  const card = document.createElement("div");
  card.className = "agent-card idle";
  card.id = `card-${a.role}`;
  card.innerHTML = `
    <div class="agent-name">${a.name}</div>
    <div class="agent-display">${a.display}</div>
    <div class="agent-state idle" id="state-${a.role}">idle</div>
    <div class="agent-task" id="task-${a.role}">—</div>
  `;
  card.addEventListener("click", () => showDetail(a));
  grid.appendChild(card);
});

// Build pod list
const podList = document.getElementById("pod-list");
PODS.forEach((pod, i) => {
  const div = document.createElement("div");
  div.className = "pod-item" + (i === 0 ? " active" : "");
  div.innerHTML = `<span class="pod-dot"></span>${pod}`;
  div.addEventListener("click", () => {
    document.querySelectorAll(".pod-item").forEach(p => p.classList.remove("active"));
    div.classList.add("active");
  });
  podList.appendChild(div);
});

function applyState(data) {
  if (!data || !data.agents) return;

  // Budget
  const spent = data.budget?.spent_usd ?? 0;
  const cap = data.budget?.cap_usd ?? 50;
  const pct = Math.min((spent / cap) * 100, 100);
  document.getElementById("budget-text").textContent = `$${spent.toFixed(2)} / $${cap.toFixed(2)}`;
  const fill = document.getElementById("budget-fill");
  fill.style.width = pct + "%";
  fill.style.background = pct > 90 ? "var(--red)" : pct > 70 ? "var(--orange)" : "var(--green)";

  // Task counts
  const t = data.tasks ?? {};
  document.getElementById("q-todo").textContent = t.todo ?? 0;
  document.getElementById("q-active").textContent = t.in_progress ?? 0;
  document.getElementById("q-review").textContent = t.review ?? 0;
  document.getElementById("q-done").textContent = t.done ?? 0;
  document.getElementById("q-failed").textContent = t.failed ?? 0;

  // Agent cards
  Object.entries(data.agents).forEach(([role, info]) => {
    const card = document.getElementById(`card-${role}`);
    const stateEl = document.getElementById(`state-${role}`);
    const taskEl = document.getElementById(`task-${role}`);
    if (!card) return;

    const state = info.state ?? "idle";
    card.className = `agent-card ${state}`;
    stateEl.className = `agent-state ${state}`;
    stateEl.textContent = state === "budget_paused" ? "paused" : state;
    if (state === "working") stateEl.classList.add("pulse");
    taskEl.textContent = info.task_id || info.last_action || "—";

    // Log entry when state changes to working
    if (state === "working" && info.task_id) {
      addLog(role, `working on ${info.task_id}`);
    } else if (info.last_action && state === "idle") {
      addLog(role, info.last_action);
    }
  });
}

function addLog(role, msg) {
  const now = new Date();
  const time = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  const entry = { time, role, msg };
  logEntries.unshift(entry);
  if (logEntries.length > 100) logEntries.pop();
  renderLog();
}

function renderLog() {
  const el = document.getElementById("activity-log");
  el.innerHTML = logEntries.slice(0, 40).map(e =>
    `<div class="log-entry">
      <span class="log-time">${e.time}</span>
      <span class="log-agent">${e.role.replace("_worker","").replace("_"," ")}</span>
      <span class="log-msg">${e.msg}</span>
    </div>`
  ).join("");
}

function showDetail(agent) {
  selectedAgent = agent.role;
  document.getElementById("detail-panel").classList.add("visible");
  document.getElementById("detail-title").textContent = `${agent.display} (${agent.name})`;
  const info = lastState?.agents?.[agent.role] ?? {};
  document.getElementById("detail-content").innerHTML =
    `State: <b>${info.state ?? "—"}</b><br>` +
    `Task: <b>${info.task_id ?? "—"}</b><br>` +
    `Last action: ${info.last_action ?? "—"}`;
  document.getElementById("detail-log").textContent =
    logEntries.filter(e => e.role === agent.role).slice(0, 20)
      .map(e => `${e.time}  ${e.msg}`).join("\n") || "No recent activity.";
}

// WebSocket
let lastState = {};
const dot = document.getElementById("status-dot");

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    dot.classList.add("connected");
    dot.title = "WebSocket connected";
  };

  ws.onmessage = (e) => {
    try {
      lastState = JSON.parse(e.data);
      applyState(lastState);
    } catch {}
  };

  ws.onclose = () => {
    dot.classList.remove("connected");
    dot.title = "WebSocket disconnected — reconnecting...";
    setTimeout(connect, 3000);
  };

  ws.onerror = () => ws.close();
}

// Also poll /state every 5s as fallback
setInterval(async () => {
  try {
    const r = await fetch("/state");
    lastState = await r.json();
    applyState(lastState);
  } catch {}
}, 5000);

connect();
</script>
</body>
</html>
```

- [ ] **Step 2: Open the dashboard in browser to verify it renders**

First start the server:
```powershell
python -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8765 --reload
```

Open `http://127.0.0.1:8765` in a browser.

Expected: Dashboard loads. Agent grid shows 11 cards. All show "idle" state. Budget bar shows $0.00/$50.00. No JS errors in browser console.

- [ ] **Step 3: Verify live updates work**

With the server running, manually edit `workspace/dashboard-state.json` to set one agent's state to `"working"`:

```powershell
$state = Get-Content workspace\dashboard-state.json | ConvertFrom-Json
$state.agents | Add-Member -NotePropertyName "manager" -NotePropertyValue @{state="working"; task_id="TEST-001"; last_action=""; updated_at=0} -Force
$state | ConvertTo-Json -Depth 5 | Out-File workspace\dashboard-state.json -Encoding utf8
```

Expected: Atlas card turns green with pulse animation within 1 second, no page refresh needed.

- [ ] **Step 4: Commit**

```powershell
git add dashboard\index.html
git commit -m "feat: add live 2D dashboard frontend with agent grid and WebSocket"
```

---

## Task 5: Dashboard Startup Script

**Files:**
- Create: `scripts/start_dashboard.py`

- [ ] **Step 1: Create `scripts/start_dashboard.py`**

```python
# scripts/start_dashboard.py
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
```

- [ ] **Step 2: Run the full test suite**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED.

- [ ] **Step 3: Commit**

```powershell
git add scripts\start_dashboard.py
git commit -m "feat: add dashboard startup script — Plan 2 complete"
```

---

## What's Next

**Plan 3** wires up Windows Scheduler (cron triggers), Tony Stocks file bridge, image/audio tool adapters with Claude tool_use, and plugin skill injection into agent system prompts.

To run dashboard + runner together:
```powershell
# Terminal 1 — dashboard
python scripts/start_dashboard.py

# Terminal 2 — runner (one cycle)
python -m runner.main

# Or with real API key for live execution:
$env:ANTHROPIC_API_KEY = "your-key"
python -m runner.main
```
