import json
import re
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
    "prospector":    ("opportunity_worker",  "opportunity_scout", "opportunity_pod"),
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
        force=True,
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


@app.post("/api/outreach/followup-sweep")
async def outreach_followup_sweep():
    """Queue one outreach_worker task to follow up every replied/interested lead
    that is not yet closed. Backs the CRM 'Queue Follow-up Sweep' button."""
    from runner.tools.task_creator import create_task

    result = create_task(
        title="Follow up warm outreach leads",
        body=(
            "Review vault/outreach/crm.md. For every lead whose status is "
            "'replied', 'interested', or 'callback' and is NOT already 'closed' "
            "or 'no_interest', send a follow-up via the lead's original channel "
            "(email or DM). Update each lead's status/notes in the CRM afterward. "
            "Use the Easy Simple Sites pitch and pricing from your system prompt."
        ),
        assigned_agent="outreach_worker",
        task_type="prospect_research",
        pod="local_outreach_pod",
        priority="high",
    )
    return result


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


@app.get("/api/spawn-gate")
async def api_spawn_gate():
    """Per-scope-key spawn-cadence state + summary + recent gate decisions.

    The Prospector scout is gated by scout_due (scheduler-state), not the spawn
    gate, so we inject a read-only row for it here — visible countdown without
    throttling the per-target one-offs (deepdive/poc_build) that must run freely."""
    from runner.scheduler.spawn_gate import gate_snapshot
    snap = gate_snapshot()
    try:
        from datetime import timedelta
        from runner.config import load_spawn_schedules
        interval = ((load_spawn_schedules() or {}).get("scout", {}) or {}).get("min_interval_minutes", 120)
        state_file = Path(__file__).parent.parent / "workspace" / "scheduler-state.json"
        last = None
        if state_file.exists():
            last = json.loads(state_file.read_text(encoding="utf-8")).get("last_scout")
        now = datetime.now()
        status, ready_in, next_allowed = "ready", None, None
        if last:
            na = datetime.fromisoformat(last) + timedelta(minutes=interval)
            next_allowed = na.isoformat()
            if now < na:
                status, ready_in = "cooldown", max(0, round((na - now).total_seconds()))
        snap.setdefault("keys", []).insert(0, {
            "key": "scout:opportunity_worker", "scope": "scout", "agent": "opportunity_worker",
            "task_type": "opportunity_scout", "configured": True,
            "min_interval_minutes": interval, "jitter_minutes": None, "max_per_day": None,
            "quiet_hours": None, "spawns_today": None, "last_spawn": last,
            "next_allowed": next_allowed, "status": status, "ready_in_seconds": ready_in,
            "last_reason": "Prospector scout (scheduler timer, not throttled)",
        })
        s = snap.setdefault("summary", {})
        s["tracked_keys"] = s.get("tracked_keys", 0) + 1
        s[("in_cooldown" if status == "cooldown" else "ready")] = s.get("in_cooldown" if status == "cooldown" else "ready", 0) + 1
    except Exception:
        pass
    return snap


# ── Spawn-schedule editor (live-editable cadence, comment-preserving) ──────────
_SCHEDULE_FILE = Path(__file__).parent.parent / "config" / "spawn-schedules.yaml"

# field -> (section heading regex, knob key, min, max). Targeted line-edits keep
# the file's explanatory comments intact (a full yaml.dump would wipe them).
_EDITABLE_KNOBS = {
    "scout_interval":       (r"^\s*scout:\s*$",          "min_interval_minutes", 1, 1440),
    "outreach_interval":    (r"^\s*prospect_research:",   "min_interval_minutes", 1, 1440),
    "outreach_max_per_day": (r"^\s*prospect_research:",   "max_per_day",          1, 500),
}


@app.get("/api/spawn-schedules")
async def api_get_spawn_schedules():
    from runner.config import load_spawn_schedules
    s = load_spawn_schedules() or {}
    pr = (s.get("by_task_type", {}) or {}).get("prospect_research", {}) or {}
    return {
        "scout_interval":       (s.get("scout", {}) or {}).get("min_interval_minutes"),
        "outreach_interval":    pr.get("min_interval_minutes"),
        "outreach_max_per_day": pr.get("max_per_day"),
        "note": "Edits apply on the next runner cycle — no restart needed.",
    }


def _set_yaml_knob(lines: list[str], section_re: str, key: str, value: int) -> bool:
    in_section = False
    section_indent = -1
    for i, line in enumerate(lines):
        if re.match(section_re, line):
            in_section = True
            section_indent = len(line) - len(line.lstrip())
            continue
        if in_section:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if stripped and not stripped.startswith("#") and indent <= section_indent:
                in_section = False
                continue
            m = re.match(rf"^(\s*{key}:\s*)(\d+)(.*)$", line)
            if m:
                lines[i] = f"{m.group(1)}{value}{m.group(3)}"
                return True
    return False


@app.post("/api/spawn-schedules")
async def api_set_spawn_schedules(request: Request):
    body = await request.json()
    if not _SCHEDULE_FILE.exists():
        return {"error": "spawn-schedules.yaml not found"}
    lines = _SCHEDULE_FILE.read_text(encoding="utf-8").splitlines()
    applied, errors = {}, []
    for field, (section_re, key, lo, hi) in _EDITABLE_KNOBS.items():
        if field not in body or body[field] is None:
            continue
        try:
            val = int(body[field])
        except (TypeError, ValueError):
            errors.append(f"{field} must be an integer")
            continue
        if not (lo <= val <= hi):
            errors.append(f"{field} must be between {lo} and {hi}")
            continue
        if _set_yaml_knob(lines, section_re, key, val):
            applied[field] = val
        else:
            errors.append(f"could not locate {field} in config")
    if errors:
        return {"ok": False, "errors": errors, "applied": applied}
    _SCHEDULE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "applied": applied,
            "note": "Saved. Applies on the next runner cycle."}


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


# ── Per-pod dashboards ────────────────────────────────────────────
# Active pods that lacked a dedicated view. outreach (CRM tab) and
# opportunity_pod/Prospector (Opportunity Board) already have theirs;
# dormant agents (Spark/Muse/Maker/Market/Frame/Echo) and infra roles
# (Scout/Guard/Ledger) are intentionally omitted.
POD_REGISTRY = {
    "forge": {"role": "heavy_worker",            "pod": "opportunity_pod"},
    "atlas": {"role": "manager",                 "pod": "management"},
    "sage":  {"role": "librarian",               "pod": "management"},
    "tony":  {"role": "market_research_worker",  "pod": "market_research_pod"},
}


def _agent_meta(role_id: str) -> dict:
    from runner.config import load_agents
    for a in load_agents().get("agents", []):
        if a.get("role_id") == role_id:
            return {
                "display_name": a.get("display_name", role_id),
                "purpose": a.get("purpose", ""),
                "task_types": a.get("allowed_task_types", []),
            }
    return {"display_name": role_id, "purpose": "", "task_types": []}


def _pod_budget(role_id: str, pod: str) -> dict:
    from runner.ledger.budget import get_pod_spend, get_pod_cap, _load_spend
    from runner.config import load_budgets
    pod_cap = get_pod_cap(pod)
    if pod_cap != float("inf"):
        return {"spent": round(get_pod_spend(pod), 2), "cap": pod_cap, "basis": "pod"}
    role_limits = load_budgets()["budgets"].get("per_role_limits", {})
    cap = (role_limits.get(role_id) or {}).get("daily_spend_limit_usd")
    spent = _load_spend().get("by_role", {}).get(role_id, 0.0)
    return {"spent": round(spent, 2), "cap": cap, "basis": "role"}


def _pod_activity(role_id: str, limit: int = 8) -> dict:
    counts = {"done": 0, "failed": 0, "todo": 0}
    recent = []
    for sub in ("done", "failed", "todo"):
        folder = TASKS_DIR / sub
        if not folder.exists():
            continue
        for f in folder.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            agent, created, title = "", "", f.stem
            for line in text.split("\n"):
                s = line.strip()
                if s.startswith("assigned_agent:"):
                    agent = s.split(":", 1)[1].strip()
                elif s.startswith("created_at:"):
                    created = s.split(":", 1)[1].strip()
                elif s.startswith("# "):
                    title = s[2:].strip()
                    break
            if agent != role_id:
                continue
            counts[sub] += 1
            recent.append({"label": title[:60], "status": sub, "when": created})
    recent.sort(key=lambda r: r["when"], reverse=True)
    return {**counts, "recent": recent[:limit]}


def _pod_status(budget: dict, activity: dict) -> str:
    cap, spent = budget.get("cap"), budget.get("spent", 0)
    pct = (spent / cap * 100) if cap else 0
    last3 = activity.get("recent", [])[:3]
    if pct >= 95 or (last3 and all(r["status"] == "failed" for r in last3)):
        return "red"
    if pct >= 70 or activity.get("failed", 0) > activity.get("done", 0):
        return "yellow"
    return "green"


def _forge_artifacts() -> dict:
    items = []
    poc_root = Path(__file__).parent.parent / "workspace" / "poc"
    if poc_root.exists():
        for d in sorted(poc_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir():
                items.append({"label": d.name, "value": "built"})
    for r in read_opportunities():
        grade = (r.get("poc") or "").strip()
        if grade and grade not in ("—", "-"):
            items.append({"label": r["slug"], "value": grade})
    return {"title": "Proof-of-Concepts & Grades", "items": items[:12],
            "empty": "No PoCs built or graded yet."}


def _atlas_artifacts() -> dict:
    items, files = [], []
    sessions_root = VAULT_DIR / "sessions"
    if sessions_root.exists():
        for day in sessions_root.iterdir():
            if day.is_dir():
                files.extend(day.glob("ATLAS*.md"))
    for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        items.append({"label": _friendly_label(f.stem), "value": ""})
    return {"title": "Recent Planning / Routing", "items": items,
            "empty": "No Atlas plans recorded yet."}


def _sage_artifacts() -> dict:
    items = []
    syn = VAULT_DIR / "synthesis" / "cross_agent_insights.md"
    if syn.exists():
        mt = datetime.fromtimestamp(syn.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        items.append({"label": "cross_agent_insights.md", "value": f"updated {mt}"})
    agents_root = VAULT_DIR / "agents"
    if agents_root.exists():
        n = len(list(agents_root.glob("*/learned_rules.md")))
        if n:
            items.append({"label": "learned_rules.md", "value": f"{n} agents"})
    return {"title": "Memory Synthesis", "items": items,
            "empty": "No synthesis yet — Sage runs weekly (Sunday night)."}


def _tony_artifacts() -> dict:
    items = []
    try:
        from runner.tools.tony_insights import INSIGHTS_FILE
        if INSIGHTS_FILE.exists():
            data = json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
            entries = data if isinstance(data, list) else data.get("insights", [])
            for e in list(entries)[-8:][::-1]:
                if isinstance(e, dict):
                    items.append({"label": e.get("category", "insight"),
                                  "value": (e.get("insight") or "")[:80]})
    except (json.JSONDecodeError, OSError, ImportError):
        pass
    return {"title": "Trading Research Insights", "items": items,
            "empty": "No Tony insights yet (TradingBotAgentProject bridge inactive)."}


_POD_ARTIFACTS = {
    "forge": _forge_artifacts, "atlas": _atlas_artifacts,
    "sage": _sage_artifacts,   "tony": _tony_artifacts,
}


@app.get("/api/pod/{key}")
async def api_pod(key: str):
    reg = POD_REGISTRY.get(key)
    if not reg:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"error": f"Unknown pod '{key}'. Valid: {list(POD_REGISTRY)}"}, status_code=404
        )
    role, pod = reg["role"], reg["pod"]
    meta = _agent_meta(role)
    budget = _pod_budget(role, pod)
    activity = _pod_activity(role)
    return {
        "key": key, "name": meta["display_name"], "agent": role, "pod": pod,
        "purpose": meta["purpose"], "task_types": meta["task_types"],
        "budget": budget, "activity": activity,
        "artifacts": _POD_ARTIFACTS[key](),
        "status": _pod_status(budget, activity),
    }


# ── Tony stock dashboard (parses vault signal ledger) ─────────────
_TONY_LEDGER = VAULT_DIR / "tony-stocks" / "signal-ledger.md"


def _parse_md_section_table(text: str, heading_contains: str) -> list[dict]:
    """Rows of the first markdown table under an H2 whose title contains the given text."""
    rows: list[dict] = []
    headers: list[str] = []
    in_section = in_table = False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("## "):
            if in_section and in_table:
                break
            in_section = heading_contains.lower() in s.lower()
            in_table = False
            headers = []
            continue
        if not in_section:
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not headers:
                headers, in_table = cells, True
            elif not all(c in ("", "—", "-") for c in cells):
                rows.append(dict(zip(headers, cells)))
        elif in_table and not s:
            break
    return rows


@app.get("/api/tony/stocks")
async def api_tony_stocks():
    if not _TONY_LEDGER.exists():
        return {"available": False, "signals": [], "metrics": {}, "sectors": [],
                "note": "No signal ledger yet — Tony writes it after his first run."}
    text = _TONY_LEDGER.read_text(encoding="utf-8", errors="ignore")
    last_updated = ""
    for line in text.split("\n"):
        if line.lower().startswith("last updated:"):
            last_updated = line.split(":", 1)[1].strip()
            break
    persistent = _parse_md_section_table(text, "Persistent Signals")
    active = _parse_md_section_table(text, "Active Signals")
    for r in persistent:
        r["tier"] = "persistent"
    for r in active:
        r["tier"] = "active"
    signals = persistent + active

    # Enrich each signal from its ticker page: conviction is in the vault now;
    # price + P/L populate from the bot's market run (None until then).
    tickers_dir = VAULT_DIR / "tickers"
    for sig in signals:
        sig["conviction"] = sig["price"] = sig["pl"] = None
        t = (sig.get("Ticker") or "").strip().upper()
        page = tickers_dir / f"{t}.md"
        if t and page.exists():
            ptext = page.read_text(encoding="utf-8", errors="ignore")
            mc = re.search(r"[Cc]onviction(?:\s+score)?[:\s|*]+(\d{1,3})", ptext)
            if mc:
                sig["conviction"] = int(mc.group(1))
            mp = re.search(r"(?:current price|last price|price)[:\s|*$]+([\d.]+)", ptext, re.IGNORECASE)
            if mp:
                sig["price"] = float(mp.group(1))

    metrics_rows = _parse_md_section_table(text, "Weekly Metrics")
    return {
        "available": True,
        "last_updated": last_updated,
        "signals": signals,
        "signals_tracked": len(signals),
        "metrics": metrics_rows[-1] if metrics_rows else {},
        "sectors": _parse_md_section_table(text, "Sector Clusters"),
        "price_note": "Price & P/L populate when the trading bot runs (live market data).",
    }
