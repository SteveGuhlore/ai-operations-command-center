import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Set
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
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

import subprocess
import sys
import threading
from datetime import datetime

VAULT_DIR = Path(__file__).parent.parent / "vault"
TASKS_DIR = Path(__file__).parent.parent / "workspace" / "tasks"

_POD_MAP = {
    "spark":         ("social_media_worker", "video_production",  "social_media_pod"),
    "maker":         ("digital_product_worker", "guide_creation", "digital_products_pod"),
    "atlas":         ("manager",             "planning",          "management"),
    "trend_scan":    ("debug_worker",        "research",          "general"),
    "full_pipeline": ("manager",             "planning",          "management"),
    "outreach":      ("outreach_worker",     "prospect_research", "local_outreach_pod"),
    "builder":       ("builder",             "site_build",        "local_outreach_pod"),
    "sage":          ("librarian",           "memory_synthesis",  "management"),
}


@app.get("/api/status")
async def api_status():
    exec_active = False
    improve_next = "unavailable"

    if sys.platform != "win32":
        try:
            r = subprocess.run(
                ["systemctl", "is-active", "execution-loop"],
                capture_output=True, text=True, timeout=5,
            )
            exec_active = r.stdout.strip() == "active"
        except Exception:
            pass

        try:
            r2 = subprocess.run(
                ["systemctl", "show", "improvement-loop.timer",
                 "--property=NextElapseUSecRealtime", "--value"],
                capture_output=True, text=True, timeout=5,
            )
            raw = r2.stdout.strip()
            if raw and raw != "0":
                # Convert microseconds since epoch to human-readable
                ts = int(raw) // 1_000_000
                improve_next = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass

    return {"execution_loop_active": exec_active, "improvement_next_run": improve_next}


@app.post("/api/trigger")
async def api_trigger(request: Request):
    body = await request.json()
    pod = body.get("pod", "")

    if pod not in _POD_MAP:
        return {"error": f"Unknown pod '{pod}'. Valid: {list(_POD_MAP)}"}

    role, task_type, pod_name = _POD_MAP[pod]
    from runner.tools.task_creator import create_task

    result = create_task(
        title=f"Manual trigger: {pod}",
        body=(
            f"Manually triggered from dashboard at {datetime.now().isoformat()}. "
            f"Run your autonomous workflow for this pod. "
            f"Use the brand and strategy configured in your system prompt."
        ),
        assigned_agent=role,
        task_type=task_type,
        pod=pod_name,
        priority="high",
    )

    # Run a cycle immediately so the task executes now rather than waiting for the next cron tick
    def _run():
        try:
            from runner.main import run_cycle
            run_cycle()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return result


@app.get("/api/analytics/agents")
async def api_analytics_agents():
    done_dir   = TASKS_DIR / "done"
    failed_dir = TASKS_DIR / "failed"
    counts: dict[str, dict] = {}

    def _tally(folder: Path, outcome: str):
        if not folder.exists():
            return
        for f in folder.glob("*.md"):
            text  = f.read_text(encoding="utf-8", errors="ignore")
            agent = "unknown"
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("assigned_agent:"):
                    agent = line.split(":", 1)[1].strip()
                    break
            if agent not in counts:
                counts[agent] = {"done": 0, "failed": 0}
            counts[agent][outcome] += 1

    _tally(done_dir,   "done")
    _tally(failed_dir, "failed")

    rows = []
    for agent, c in sorted(counts.items()):
        total       = c["done"] + c["failed"]
        success_pct = round(c["done"] / total * 100) if total else 0
        rows.append({"agent": agent, "done": c["done"], "failed": c["failed"],
                     "total": total, "success_pct": success_pct})
    rows.sort(key=lambda r: r["total"], reverse=True)
    return {"agents": rows}


@app.get("/api/outreach/stats")
async def api_outreach_stats():
    crm_file   = VAULT_DIR / "outreach" / "crm.md"
    queue_file = VAULT_DIR / "outreach" / "dm-queue.md"
    stats = {
        "total": 0, "emailed": 0, "dm_sent": 0, "call_queued": 0,
        "followed_up": 0, "replied": 0, "closed": 0, "no_interest": 0,
        "dm_queue_count": 0, "conversion_pct": 0, "recent": [],
    }

    status_aliases = {
        "email_sent": "emailed",
        "dm_queued":  "dm_sent",
    }
    if crm_file.exists():
        for line in crm_file.read_text(encoding="utf-8").split("\n"):
            if not line.startswith("|") or "Business" in line or line.startswith("|---"):
                continue
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 7:
                continue
            status = parts[5].lower()
            status = status_aliases.get(status, status)
            stats["total"] += 1
            if status in stats:
                stats[status] += 1
            stats["recent"].append({
                    "business": parts[0], "type": parts[1], "city": parts[2],
                    "contact": parts[3], "channel": parts[4],
                    "status": parts[5], "date": parts[6],
                    "notes": parts[7] if len(parts) > 7 else "",
            })

    if queue_file.exists():
        for line in queue_file.read_text(encoding="utf-8").split("\n"):
            if line.startswith("|") and "Business" not in line and not line.startswith("|---"):
                stats["dm_queue_count"] += 1

    if stats["total"]:
        stats["conversion_pct"] = round(stats["closed"] / stats["total"] * 100)
    return stats


CALL_OUTCOMES = {"answered", "no_answer", "interested", "not_interested", "callback", "emailed", "dm_sent", "call_queued", "followed_up", "replied", "closed", "no_interest"}

@app.post("/api/outreach/update-status")
async def update_outreach_status(request: Request):
    data = await request.json()
    business = (data.get("business") or "").strip()
    new_status = (data.get("status") or "").strip()
    new_notes  = (data.get("notes")  or "").strip()
    if not business:
        return {"error": "business required"}
    crm_file = VAULT_DIR / "outreach" / "crm.md"
    if not crm_file.exists():
        return {"error": "CRM not found"}
    lines = crm_file.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("|") or "Business" in line or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 6 and parts[0].lower() == business.lower():
            if new_status:
                parts[5] = new_status
            if new_notes and len(parts) > 7:
                parts[7] = new_notes
            elif new_notes:
                while len(parts) < 8:
                    parts.append("")
                parts[7] = new_notes
            lines[i] = "| " + " | ".join(parts) + " |"
            crm_file.write_text("\n".join(lines), encoding="utf-8")
            return {"success": True}
    return {"error": f"'{business}' not found in CRM"}


def read_opportunities() -> list[dict]:
    """Parse vault/opportunities/ledger.md into rows for the Opportunity Board."""
    ledger = VAULT_DIR / "opportunities" / "ledger.md"
    if not ledger.exists():
        return []
    rows = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| slug") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9:
            continue
        rows.append({
            "slug": cells[0], "composite": cells[1], "phase": cells[2],
            "poc": cells[3], "system_fit": cells[4], "est_rev_mo": cells[5],
            "status": cells[6], "pod": cells[7], "updated": cells[8],
        })
    rows.sort(key=lambda r: float(r["composite"]) if r["composite"].replace(".", "").isdigit() else 0, reverse=True)
    return rows


def read_pod_spend(pod: str = "opportunity_pod") -> dict:
    """Real spend + cap for the opportunity pod."""
    from runner.ledger.budget import get_pod_spend, get_pod_cap
    cap = get_pod_cap(pod)
    return {"spent": round(get_pod_spend(pod), 2), "cap": (None if cap == float("inf") else cap)}


@app.get("/api/opportunities")
async def api_opportunities():
    return {"opportunities": read_opportunities(), "opportunity_spend": read_pod_spend()}


def _friendly_label(task_id: str) -> str:
    p = task_id.split("-")
    if task_id.startswith("TONY-DAILY-BRIEF-") and len(p) >= 4:
        d = p[-1]
        return f"Tony Brief · {d[4:6]}/{d[6:8]}" if len(d) == 8 else task_id
    if task_id.startswith("TONY-TUESDAY-PREP-") and len(p) >= 4:
        d = p[-1]
        return f"Tony Tue Prep · {d[4:6]}/{d[6:8]}" if len(d) == 8 else task_id
    if task_id.startswith("TONY-WEEKLY-") and len(p) >= 3:
        d = p[-1]
        return f"Tony Weekly · {d[4:6]}/{d[6:8]}" if len(d) == 8 else task_id
    if task_id.startswith("ATLAS-PLAN-") and len(p) >= 3:
        d = p[2]
        return f"Atlas Plan · {d[4:6]}/{d[6:8]}" if len(d) == 8 else task_id
    return task_id[:28]


@app.get("/api/vault/feed")
async def api_vault_feed():
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = VAULT_DIR / "sessions" / today
    if not session_dir.exists():
        return {"sessions": [], "date": today}

    sessions = []
    for f in sorted(session_dir.glob("*.md"), reverse=True)[:20]:
        text = f.read_text(encoding="utf-8")
        status = "done"
        summary = ""
        for line in text.split("\n"):
            if line.startswith("status:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("summary:"):
                summary = line.split(":", 1)[1].strip()
            elif line == "---" and summary:
                break
        sessions.append({
            "task_id": f.stem,
            "label": _friendly_label(f.stem),
            "status": status,
            "summary": summary,
        })

    return {"sessions": sessions, "date": today}
