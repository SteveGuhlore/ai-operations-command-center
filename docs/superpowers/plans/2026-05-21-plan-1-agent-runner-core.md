# Agent Runner Core — Implementation Plan 1 of 3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python agent runner that reads tasks from the Command Center queue, routes them to the correct agent role, fires Claude API calls, tracks spend via Ledger, and writes dashboard state — making all 11 agents actually execute work autonomously.

**Architecture:** A Python service (`runner/`) sits inside the Command Center directory and reads YAML-frontmatter task files from `workspace/tasks/todo/`. It routes each task to an agent role, calls the Claude API with a role-specific system prompt, moves the task through the status pipeline (todo → in_progress → done/failed), and writes a `dashboard-state.json` that the dashboard (Plan 2) reads. Ledger enforces a configurable daily spend cap.

**Tech Stack:** Python 3.11+, `anthropic` SDK, `pyyaml`, `pytest`. No external dependencies beyond these.

---

## File Map

```
runner/
  __init__.py
  main.py                    # entry point — run_cycle() dispatches tasks
  config.py                  # loads YAML config files
  agents/
    __init__.py
    base.py                  # AgentBase class — wraps Claude API call + cost tracking
    prompts.py               # builds per-role system prompts from .md + agents.yaml
  tasks/
    __init__.py
    reader.py                # reads .md task files from workspace/tasks/todo/
    router.py                # maps task_type → role_id using agents.yaml
    locker.py                # creates/releases/checks workspace/locks/*.lock
    transitions.py           # moves task files between status folders
  ledger/
    __init__.py
    budget.py                # daily spend tracking + cap enforcement
  state/
    __init__.py
    writer.py                # writes workspace/dashboard-state.json
config/
  agents.yaml                # copy of agents.example.yaml (rename, fill real values)
  budgets.yaml               # copy of budgets.example.yaml (fill real dollar caps)
  automation-level.yaml      # NEW — controls which action levels are enabled
tests/
  runner/
    __init__.py
    test_reader.py
    test_router.py
    test_locker.py
    test_transitions.py
    test_budget.py
    test_prompts.py
    test_state_writer.py
    test_main.py
requirements.txt
```

---

## Task 1: Project Setup

**Files:**
- Create: `runner/__init__.py`
- Create: `runner/agents/__init__.py`
- Create: `runner/tasks/__init__.py`
- Create: `runner/ledger/__init__.py`
- Create: `runner/state/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/runner/__init__.py`
- Create: `requirements.txt`
- Create: `config/agents.yaml`
- Create: `config/budgets.yaml`
- Create: `config/automation-level.yaml`

- [ ] **Step 1: Create all empty `__init__.py` files**

Run in the Command Center root:
```powershell
New-Item -ItemType Directory -Force runner, runner\agents, runner\tasks, runner\ledger, runner\state, tests, tests\runner
"" | Out-File runner\__init__.py -Encoding utf8
"" | Out-File runner\agents\__init__.py -Encoding utf8
"" | Out-File runner\tasks\__init__.py -Encoding utf8
"" | Out-File runner\ledger\__init__.py -Encoding utf8
"" | Out-File runner\state\__init__.py -Encoding utf8
"" | Out-File tests\__init__.py -Encoding utf8
"" | Out-File tests\runner\__init__.py -Encoding utf8
```

- [ ] **Step 2: Create `requirements.txt`**

```
anthropic>=0.40.0
pyyaml>=6.0
pytest>=8.0
pytest-mock>=3.12
```

- [ ] **Step 3: Install dependencies**

```powershell
pip install -r requirements.txt
```

Expected output: Successfully installed anthropic, pyyaml, pytest, pytest-mock (and their deps).

- [ ] **Step 4: Create `config/agents.yaml`**

Copy `config/agents.example.yaml` to `config/agents.yaml`. No edits needed — the example is already complete.

```powershell
Copy-Item config\agents.example.yaml config\agents.yaml
```

- [ ] **Step 5: Create `config/budgets.yaml`**

Create `config/budgets.yaml` with real values (replace all PLACEHOLDERs):

```yaml
budgets:
  daily_limits:
    total_token_limit: 5000000
    total_spend_limit_usd: 50.00

  per_role_limits:
    manager:
      daily_spend_limit_usd: 15.00
      daily_token_limit: 1000000
    heavy_worker:
      daily_spend_limit_usd: 10.00
      daily_token_limit: 800000
    debug_worker:
      daily_spend_limit_usd: 5.00
      daily_token_limit: 600000
    content_worker:
      daily_spend_limit_usd: 5.00
      daily_token_limit: 600000
    media_worker:
      daily_spend_limit_usd: 5.00
      daily_token_limit: 400000
    audio_worker:
      daily_spend_limit_usd: 3.00
      daily_token_limit: 400000
    guard_worker:
      daily_spend_limit_usd: 2.00
      daily_token_limit: 300000
    budget_worker:
      daily_spend_limit_usd: 2.00
      daily_token_limit: 300000

  retry_limits:
    default_max_retries: 2
    manager: 1
    heavy_worker: 2
    debug_worker: 2
    content_worker: 2
    media_worker: 2
    audio_worker: 2
    guard_worker: 1
    budget_worker: 1

  alert_thresholds:
    warn_at_percent_of_daily_budget: 70
    pause_noncritical_work_at_percent_of_daily_budget: 95

  shutdown_threshold:
    stop_all_nonapproved_work_at_percent_of_daily_budget: 100
```

- [ ] **Step 6: Create `config/automation-level.yaml`**

```yaml
automation:
  current_level: 2
  # Level 2: draft generation, no human approval gates
  # Level 3: enables Etsy publishing, social posting, paid campaigns
  # To advance: change current_level to 3

  level_3_actions:
    etsy_publish: false
    social_post: false
    paid_campaign: false
```

- [ ] **Step 7: Verify structure**

```powershell
Get-ChildItem -Recurse runner | Select-Object FullName
Get-ChildItem config\*.yaml | Select-Object Name
```

Expected: runner/ tree + agents.yaml, budgets.yaml, automation-level.yaml.

- [ ] **Step 8: Commit**

```powershell
git init  # if not already a repo
git add runner\ tests\ requirements.txt config\agents.yaml config\budgets.yaml config\automation-level.yaml
git commit -m "feat: scaffold runner structure and config files"
```

---

## Task 2: Config Loader

**Files:**
- Create: `runner/config.py`
- Create: `tests/runner/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_config.py
from runner.config import load_agents, load_budgets, load_automation_level

def test_load_agents_returns_agent_list():
    data = load_agents()
    assert "agents" in data
    assert any(a["role_id"] == "manager" for a in data["agents"])

def test_load_budgets_returns_daily_limit():
    data = load_budgets()
    assert data["budgets"]["daily_limits"]["total_spend_limit_usd"] == 50.0

def test_load_automation_level_returns_level():
    data = load_automation_level()
    assert data["automation"]["current_level"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_config.py -v
```

Expected: 3 errors — `ModuleNotFoundError: No module named 'runner.config'`

- [ ] **Step 3: Write `runner/config.py`**

```python
# runner/config.py
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def _load(relative_path: str) -> dict:
    path = BASE_DIR / relative_path
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_agents() -> dict:
    return _load("config/agents.yaml")


def load_budgets() -> dict:
    return _load("config/budgets.yaml")


def load_automation_level() -> dict:
    return _load("config/automation-level.yaml")
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_config.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\config.py tests\runner\test_config.py
git commit -m "feat: add config loader for agents, budgets, automation-level"
```

---

## Task 3: Task Reader

**Files:**
- Create: `runner/tasks/reader.py`
- Create: `tests/runner/test_reader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_reader.py
from pathlib import Path
import pytest
from runner.tasks.reader import parse_task_file, read_todo_tasks

SAMPLE_TASK = """\
---
task_id: TEST-001
assigned_agent: debug_worker
status: todo
priority: high
pod: app_saas_pod
task_type: validation
---

# Test Task

## Goal
Check environment.
"""

def test_parse_task_file_extracts_frontmatter(tmp_path):
    task_file = tmp_path / "TEST-001-test.md"
    task_file.write_text(SAMPLE_TASK, encoding="utf-8")
    task = parse_task_file(task_file)
    assert task["task_id"] == "TEST-001"
    assert task["assigned_agent"] == "debug_worker"
    assert task["status"] == "todo"
    assert task["task_type"] == "validation"

def test_parse_task_file_includes_body(tmp_path):
    task_file = tmp_path / "TEST-001-test.md"
    task_file.write_text(SAMPLE_TASK, encoding="utf-8")
    task = parse_task_file(task_file)
    assert "Check environment" in task["body"]

def test_parse_task_file_raises_on_bad_format(tmp_path):
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("no frontmatter here", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid task format"):
        parse_task_file(bad_file)

def test_read_todo_tasks_returns_list(tmp_path, monkeypatch):
    todo_dir = tmp_path / "workspace" / "tasks" / "todo"
    todo_dir.mkdir(parents=True)
    (todo_dir / "TEST-001-test.md").write_text(SAMPLE_TASK, encoding="utf-8")
    
    import runner.tasks.reader as reader_module
    monkeypatch.setattr(reader_module, "TASKS_DIR", tmp_path / "workspace" / "tasks")
    
    tasks = read_todo_tasks()
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "TEST-001"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_reader.py -v
```

Expected: 4 errors — `ModuleNotFoundError: No module named 'runner.tasks.reader'`

- [ ] **Step 3: Write `runner/tasks/reader.py`**

```python
# runner/tasks/reader.py
import re
from pathlib import Path
import yaml

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def parse_task_file(path: Path) -> dict:
    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(f"Invalid task format: {path}")
    frontmatter = yaml.safe_load(match.group(1))
    frontmatter["body"] = match.group(2).strip()
    frontmatter["file_path"] = str(path)
    return frontmatter


def read_todo_tasks() -> list[dict]:
    todo_dir = TASKS_DIR / "todo"
    return [parse_task_file(f) for f in sorted(todo_dir.glob("*.md"))]
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_reader.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\tasks\reader.py tests\runner\test_reader.py
git commit -m "feat: add task file reader with frontmatter parsing"
```

---

## Task 4: Lock File Manager

**Files:**
- Create: `runner/tasks/locker.py`
- Create: `tests/runner/test_locker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_locker.py
import pytest
from runner.tasks import locker as locker_module


def test_acquire_lock_creates_lock_file(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    result = locker_module.acquire_lock("TASK-001", "debug_worker")
    assert result is True
    assert (tmp_path / "TASK-001.lock").exists()


def test_acquire_lock_fails_if_already_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.acquire_lock("TASK-001", "debug_worker")
    result = locker_module.acquire_lock("TASK-001", "heavy_worker")
    assert result is False


def test_release_lock_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.acquire_lock("TASK-001", "debug_worker")
    locker_module.release_lock("TASK-001")
    assert not (tmp_path / "TASK-001.lock").exists()


def test_release_lock_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    locker_module.release_lock("TASK-999")  # no error on missing lock


def test_is_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(locker_module, "LOCKS_DIR", tmp_path)
    assert locker_module.is_locked("TASK-001") is False
    locker_module.acquire_lock("TASK-001", "debug_worker")
    assert locker_module.is_locked("TASK-001") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_locker.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/tasks/locker.py`**

```python
# runner/tasks/locker.py
import json
import time
from pathlib import Path

LOCKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "locks"


def acquire_lock(task_id: str, agent_role: str) -> bool:
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        return False
    lock_path.write_text(json.dumps({
        "task_id": task_id,
        "agent_role": agent_role,
        "acquired_at": time.time(),
    }), encoding="utf-8")
    return True


def release_lock(task_id: str) -> None:
    lock_path = LOCKS_DIR / f"{task_id}.lock"
    if lock_path.exists():
        lock_path.unlink()


def is_locked(task_id: str) -> bool:
    return (LOCKS_DIR / f"{task_id}.lock").exists()
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_locker.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\tasks\locker.py tests\runner\test_locker.py
git commit -m "feat: add lock file manager for task concurrency"
```

---

## Task 5: Task Status Transitions

**Files:**
- Create: `runner/tasks/transitions.py`
- Create: `tests/runner/test_transitions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_transitions.py
import pytest
from pathlib import Path
from runner.tasks import transitions as trans_module

SAMPLE_TASK = """\
---
task_id: TEST-001
assigned_agent: debug_worker
status: todo
priority: high
---

# Test Task
"""

def _setup_task(base: Path, status: str) -> Path:
    folder = base / status
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "TEST-001-test.md"
    f.write_text(SAMPLE_TASK, encoding="utf-8")
    return f


def test_move_task_moves_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    _setup_task(tmp_path, "todo")
    dst = trans_module.move_task("TEST-001", "todo", "in_progress")
    assert dst.exists()
    assert not (tmp_path / "todo" / "TEST-001-test.md").exists()


def test_move_task_updates_status_in_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    _setup_task(tmp_path, "todo")
    dst = trans_module.move_task("TEST-001", "todo", "in_progress")
    content = dst.read_text(encoding="utf-8")
    assert "status: in_progress" in content


def test_move_task_raises_if_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    (tmp_path / "todo").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        trans_module.move_task("MISSING-999", "todo", "in_progress")


def test_write_task_output_appends_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(trans_module, "TASKS_DIR", tmp_path)
    folder = tmp_path / "in_progress"
    folder.mkdir(parents=True)
    (folder / "TEST-001-test.md").write_text(SAMPLE_TASK, encoding="utf-8")
    trans_module.write_task_output("TEST-001", "All checks passed.", "in_progress")
    content = (folder / "TEST-001-test.md").read_text(encoding="utf-8")
    assert "All checks passed." in content
    assert "## Agent Output" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_transitions.py -v
```

Expected: 4 errors — module not found.

- [ ] **Step 3: Write `runner/tasks/transitions.py`**

```python
# runner/tasks/transitions.py
import re
from pathlib import Path

TASKS_DIR = Path(__file__).parent.parent.parent / "workspace" / "tasks"

_STATUS_RE = re.compile(r"(^status:\s*)(\w+)", re.MULTILINE)


def move_task(task_id: str, from_status: str, to_status: str) -> Path:
    src_dir = TASKS_DIR / from_status
    dst_dir = TASKS_DIR / to_status
    dst_dir.mkdir(parents=True, exist_ok=True)

    matches = list(src_dir.glob(f"*{task_id}*.md"))
    if not matches:
        raise FileNotFoundError(f"Task {task_id} not found in {from_status}/")

    src = matches[0]
    content = _STATUS_RE.sub(f"\\g<1>{to_status}", src.read_text(encoding="utf-8"))
    dst = dst_dir / src.name
    dst.write_text(content, encoding="utf-8")
    src.unlink()
    return dst


def write_task_output(task_id: str, output: str, status: str) -> None:
    task_dir = TASKS_DIR / status
    matches = list(task_dir.glob(f"*{task_id}*.md"))
    if not matches:
        return
    path = matches[0]
    content = path.read_text(encoding="utf-8")
    path.write_text(content + f"\n\n## Agent Output\n\n{output}\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_transitions.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\tasks\transitions.py tests\runner\test_transitions.py
git commit -m "feat: add task status transition and output writing"
```

---

## Task 6: Budget Tracker

**Files:**
- Create: `runner/ledger/budget.py`
- Create: `tests/runner/test_budget.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_budget.py
import json
import pytest
from datetime import date
from pathlib import Path
from runner.ledger import budget as budget_module


def _patch_budget(monkeypatch, tmp_path, cap: float = 50.0):
    monkeypatch.setattr(budget_module, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget_module, "SPEND_FILE", tmp_path / "daily-spend.json")
    monkeypatch.setattr(
        budget_module,
        "get_daily_cap",
        lambda: cap,
    )


def test_record_spend_creates_file(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    budget_module.record_spend("debug_worker", 0.05)
    data = json.loads((tmp_path / "daily-spend.json").read_text())
    assert data["total_usd"] == pytest.approx(0.05)
    assert data["by_role"]["debug_worker"] == pytest.approx(0.05)


def test_record_spend_accumulates(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    budget_module.record_spend("debug_worker", 0.05)
    budget_module.record_spend("debug_worker", 0.10)
    assert budget_module.get_daily_spend() == pytest.approx(0.15)


def test_is_budget_exceeded_false_under_cap(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path, cap=50.0)
    budget_module.record_spend("manager", 5.00)
    assert budget_module.is_budget_exceeded() is False


def test_is_budget_exceeded_true_at_cap(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path, cap=5.00)
    budget_module.record_spend("manager", 5.00)
    assert budget_module.is_budget_exceeded() is True


def test_spend_resets_on_new_day(tmp_path, monkeypatch):
    _patch_budget(monkeypatch, tmp_path)
    spend_file = tmp_path / "daily-spend.json"
    # Write yesterday's data
    spend_file.write_text(json.dumps({
        "date": "2000-01-01",
        "total_usd": 999.0,
        "by_role": {}
    }))
    assert budget_module.get_daily_spend() == pytest.approx(0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_budget.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/ledger/budget.py`**

```python
# runner/ledger/budget.py
import json
from datetime import date
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
SPEND_FILE = LEDGER_DIR / "daily-spend.json"


def _load_spend() -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not SPEND_FILE.exists():
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}}
    data = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}}
    return data


def _save_spend(data: dict) -> None:
    SPEND_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_spend(role_id: str, cost_usd: float) -> None:
    data = _load_spend()
    data["total_usd"] = round(data["total_usd"] + cost_usd, 6)
    data["by_role"][role_id] = round(data["by_role"].get(role_id, 0.0) + cost_usd, 6)
    _save_spend(data)


def get_daily_spend() -> float:
    return _load_spend()["total_usd"]


def get_daily_cap() -> float:
    from runner.config import load_budgets
    return load_budgets()["budgets"]["daily_limits"]["total_spend_limit_usd"]


def is_budget_exceeded() -> bool:
    return get_daily_spend() >= get_daily_cap()
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_budget.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\ledger\budget.py tests\runner\test_budget.py
git commit -m "feat: add Ledger daily spend tracker with budget cap enforcement"
```

---

## Task 7: System Prompt Builder

**Files:**
- Create: `runner/agents/prompts.py`
- Create: `tests/runner/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_prompts.py
from runner.agents.prompts import build_system_prompt


def test_prompt_contains_role_id():
    prompt = build_system_prompt("manager")
    assert "manager" in prompt


def test_prompt_contains_display_name():
    prompt = build_system_prompt("manager")
    assert "Atlas" in prompt


def test_prompt_contains_purpose():
    prompt = build_system_prompt("heavy_worker")
    assert "Forge" in prompt
    # purpose from agents.yaml
    assert "implementation" in prompt.lower()


def test_prompt_for_unknown_role_returns_generic():
    prompt = build_system_prompt("nonexistent_role")
    assert "nonexistent_role" in prompt


def test_all_defined_roles_build_without_error():
    roles = [
        "manager", "heavy_worker", "debug_worker", "content_worker",
        "media_worker", "audio_worker", "guard_worker", "budget_worker",
        "digital_product_worker", "marketing_worker",
    ]
    for role in roles:
        prompt = build_system_prompt(role)
        assert len(prompt) > 50, f"Prompt too short for {role}"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_prompts.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/agents/prompts.py`**

```python
# runner/agents/prompts.py
from pathlib import Path
from runner.config import load_agents

BASE_DIR = Path(__file__).parent.parent.parent

_ROLE_MD_FILES = {
    "manager": "agents/manager.md",
    "heavy_worker": "agents/heavy_worker.md",
    "debug_worker": "agents/debug_worker.md",
}


def _load_agent_md(role_id: str) -> str:
    filename = _ROLE_MD_FILES.get(role_id)
    if not filename:
        return ""
    path = BASE_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _get_agent_config(role_id: str) -> dict:
    agents = load_agents()
    for agent in agents["agents"]:
        if agent["role_id"] == role_id:
            return agent
    return {}


def build_system_prompt(role_id: str) -> str:
    config = _get_agent_config(role_id)
    md = _load_agent_md(role_id)

    parts = []
    if md:
        parts.append(md)

    display_name = config.get("display_name", role_id)
    purpose = config.get("purpose", "")
    allowed_types = config.get("allowed_task_types", [])

    parts.append(f"Your role: {role_id}")
    parts.append(f"Display name: {display_name}")
    if purpose:
        parts.append(f"Purpose: {purpose}")
    if allowed_types:
        parts.append(f"Allowed task types: {', '.join(allowed_types)}")

    parts.append(
        "\nComplete the assigned task fully. Write your output clearly and concisely. "
        "Begin immediately — do not explain what you are about to do, just do it."
    )

    return "\n\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_prompts.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\agents\prompts.py tests\runner\test_prompts.py
git commit -m "feat: add per-role system prompt builder"
```

---

## Task 8: Task Router

**Files:**
- Create: `runner/tasks/router.py`
- Create: `tests/runner/test_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_router.py
from runner.tasks.router import route_task


def test_routes_validation_to_debug_worker():
    task = {"task_type": "validation", "assigned_agent": "debug_worker"}
    assert route_task(task) == "debug_worker"


def test_routes_implementation_to_heavy_worker():
    task = {"task_type": "implementation"}
    assert route_task(task) == "heavy_worker"


def test_routes_content_drafting_to_content_worker():
    task = {"task_type": "content_drafting"}
    assert route_task(task) == "content_worker"


def test_falls_back_to_assigned_agent_when_type_unknown():
    task = {"task_type": "unknown_type_xyz", "assigned_agent": "heavy_worker"}
    assert route_task(task) == "heavy_worker"


def test_falls_back_to_debug_worker_when_nothing_matches():
    task = {"task_type": "unknown_type_xyz"}
    assert route_task(task) == "debug_worker"


def test_uses_assigned_agent_when_no_task_type():
    task = {"assigned_agent": "manager"}
    assert route_task(task) == "manager"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_router.py -v
```

Expected: 6 errors — module not found.

- [ ] **Step 3: Write `runner/tasks/router.py`**

```python
# runner/tasks/router.py
from runner.config import load_agents

_routing_table: dict[str, str] | None = None


def _build_routing_table() -> dict[str, str]:
    agents_data = load_agents()
    table: dict[str, str] = {}
    for agent in agents_data["agents"]:
        role_id = agent["role_id"]
        for task_type in agent.get("allowed_task_types", []):
            if task_type not in table:
                table[task_type] = role_id
    return table


def route_task(task: dict) -> str:
    global _routing_table
    if _routing_table is None:
        _routing_table = _build_routing_table()

    task_type = task.get("task_type")
    if task_type and task_type in _routing_table:
        return _routing_table[task_type]

    assigned = task.get("assigned_agent")
    if assigned:
        return assigned

    return "debug_worker"
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_router.py -v
```

Expected: 6 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\tasks\router.py tests\runner\test_router.py
git commit -m "feat: add task router mapping task_type to agent role"
```

---

## Task 9: Claude API Base Client

**Files:**
- Create: `runner/agents/base.py`
- Create: `tests/runner/test_base.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_base.py
import pytest
from unittest.mock import MagicMock, patch
from runner.agents.base import AgentBase, calculate_cost


def test_calculate_cost_opus():
    cost = calculate_cost("claude-opus-4-7", 1_000_000, 1_000_000)
    assert cost == pytest.approx(90.0)  # (15 + 75) per million


def test_calculate_cost_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)  # (3 + 15) per million


def test_calculate_cost_haiku():
    cost = calculate_cost("claude-haiku-4-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(4.8)  # (0.8 + 4.0) per million


def test_agent_run_returns_output(monkeypatch):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Task completed successfully.")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    with patch("runner.agents.base.anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = mock_response

        with patch("runner.agents.base.record_spend"):
            agent = AgentBase("debug_worker", "claude-haiku-4-5", "You are Scout.")
            task = {"task_id": "TEST-001", "body": "Check environment."}
            result = agent.run(task)

    assert result["output"] == "Task completed successfully."
    assert result["task_id"] == "TEST-001"
    assert result["role_id"] == "debug_worker"
    assert result["cost_usd"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_base.py -v
```

Expected: 5 errors — module not found.

- [ ] **Step 3: Write `runner/agents/base.py`**

```python
# runner/agents/base.py
import anthropic
from runner.ledger.budget import record_spend

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7":   (15.0, 75.0),
    "claude-sonnet-4-6": (3.0,  15.0),
    "claude-haiku-4-5":  (0.8,   4.0),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = MODEL_PRICING.get(model, (3.0, 15.0))
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


class AgentBase:
    def __init__(self, role_id: str, model: str, system_prompt: str):
        self.role_id = role_id
        self.model = model
        self.system_prompt = system_prompt
        self.client = anthropic.Anthropic()

    def run(self, task: dict) -> dict:
        task_text = f"# Task: {task.get('task_id', 'unknown')}\n\n{task.get('body', '')}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": task_text}],
        )

        output_text = response.content[0].text
        cost = calculate_cost(self.model, response.usage.input_tokens, response.usage.output_tokens)
        record_spend(self.role_id, cost)

        return {
            "role_id": self.role_id,
            "task_id": task.get("task_id"),
            "output": output_text,
            "cost_usd": cost,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_base.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\agents\base.py tests\runner\test_base.py
git commit -m "feat: add Claude API base client with cost tracking"
```

---

## Task 10: Dashboard State Writer

**Files:**
- Create: `runner/state/writer.py`
- Create: `tests/runner/test_state_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_state_writer.py
import json
from pathlib import Path
from runner.state import writer as writer_module


def _patch_writer(monkeypatch, tmp_path):
    state_file = tmp_path / "dashboard-state.json"
    monkeypatch.setattr(writer_module, "STATE_FILE", state_file)
    monkeypatch.setattr(writer_module, "_agent_states", {})
    # Patch budget functions to avoid file I/O
    monkeypatch.setattr(writer_module, "get_daily_spend", lambda: 2.14)
    monkeypatch.setattr(writer_module, "get_daily_cap", lambda: 50.0)
    # Patch task counting to avoid real filesystem
    monkeypatch.setattr(writer_module, "_count_tasks", lambda: {
        "todo": 5, "in_progress": 2, "review": 1, "done": 10, "failed": 0
    })
    return state_file


def test_update_agent_state_writes_file(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("debug_worker", "working", "TASK-001")
    data = json.loads(state_file.read_text())
    assert data["agents"]["debug_worker"]["state"] == "working"
    assert data["agents"]["debug_worker"]["task_id"] == "TASK-001"


def test_state_file_includes_budget(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("manager", "idle")
    data = json.loads(state_file.read_text())
    assert data["budget"]["spent_usd"] == 2.14
    assert data["budget"]["cap_usd"] == 50.0


def test_state_file_includes_task_counts(tmp_path, monkeypatch):
    state_file = _patch_writer(monkeypatch, tmp_path)
    writer_module.update_agent_state("manager", "idle")
    data = json.loads(state_file.read_text())
    assert data["tasks"]["todo"] == 5
    assert data["tasks"]["done"] == 10
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_state_writer.py -v
```

Expected: 3 errors — module not found.

- [ ] **Step 3: Write `runner/state/writer.py`**

```python
# runner/state/writer.py
import json
import time
from pathlib import Path
from runner.ledger.budget import get_daily_spend, get_daily_cap

STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "dashboard-state.json"

_agent_states: dict[str, dict] = {}


def _count_tasks() -> dict:
    base = Path(__file__).parent.parent.parent / "workspace" / "tasks"
    statuses = ["todo", "in_progress", "review", "done", "failed"]
    return {s: len(list((base / s).glob("*.md"))) for s in statuses}


def update_agent_state(
    role_id: str,
    state: str,
    task_id: str = "",
    last_action: str = "",
) -> None:
    _agent_states[role_id] = {
        "state": state,
        "task_id": task_id,
        "last_action": last_action,
        "updated_at": time.time(),
    }
    _flush()


def _flush() -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "updated_at": time.time(),
        "agents": _agent_states,
        "tasks": _count_tasks(),
        "budget": {
            "spent_usd": get_daily_spend(),
            "cap_usd": get_daily_cap(),
        },
    }, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_state_writer.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```powershell
git add runner\state\writer.py tests\runner\test_state_writer.py
git commit -m "feat: add dashboard state file writer"
```

---

## Task 11: Runner Main — Orchestration Loop

**Files:**
- Create: `runner/main.py`
- Create: `tests/runner/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_main.py
from unittest.mock import patch, MagicMock
import pytest


def _make_task(task_id="TEST-001", task_type="validation", assigned="debug_worker"):
    return {
        "task_id": task_id,
        "task_type": task_type,
        "assigned_agent": assigned,
        "body": "Check environment.",
        "file_path": f"workspace/tasks/todo/{task_id}-test.md",
    }


def test_run_cycle_skips_when_budget_exceeded():
    with patch("runner.main.is_budget_exceeded", return_value=True):
        with patch("runner.main.read_todo_tasks") as mock_read:
            from runner.main import run_cycle
            run_cycle()
            mock_read.assert_not_called()


def test_run_cycle_dispatches_tasks():
    mock_result = {"task_id": "TEST-001", "output": "done", "cost_usd": 0.01}
    with patch("runner.main.is_budget_exceeded", return_value=False):
        with patch("runner.main.read_todo_tasks", return_value=[_make_task()]):
            with patch("runner.main.run_task", return_value=mock_result) as mock_run:
                from runner.main import run_cycle
                run_cycle()
                mock_run.assert_called_once()


def test_run_task_acquires_lock_and_calls_agent():
    mock_result = {"task_id": "TEST-001", "output": "done", "cost_usd": 0.01,
                   "role_id": "debug_worker", "input_tokens": 100, "output_tokens": 50}
    with patch("runner.main.acquire_lock", return_value=True):
        with patch("runner.main.release_lock"):
            with patch("runner.main.move_task"):
                with patch("runner.main.write_task_output"):
                    with patch("runner.main.update_agent_state"):
                        with patch("runner.main.AgentBase") as mock_agent_cls:
                            mock_agent = MagicMock()
                            mock_agent.run.return_value = mock_result
                            mock_agent_cls.return_value = mock_agent
                            from runner.main import run_task
                            result = run_task(_make_task())
                            assert result["task_id"] == "TEST-001"


def test_run_task_skips_when_already_locked():
    with patch("runner.main.acquire_lock", return_value=False):
        from runner.main import run_task
        result = run_task(_make_task())
        assert result.get("skipped") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/runner/test_main.py -v
```

Expected: 4 errors — module not found.

- [ ] **Step 3: Write `runner/main.py`**

```python
# runner/main.py
import concurrent.futures
import logging

from runner.agents.base import AgentBase
from runner.agents.prompts import build_system_prompt
from runner.ledger.budget import is_budget_exceeded
from runner.state.writer import update_agent_state
from runner.tasks.locker import acquire_lock, release_lock
from runner.tasks.reader import read_todo_tasks
from runner.tasks.router import route_task
from runner.tasks.transitions import move_task, write_task_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

MODELS: dict[str, str] = {
    "manager":                "claude-opus-4-7",
    "heavy_worker":           "claude-sonnet-4-6",
    "debug_worker":           "claude-haiku-4-5",
    "content_worker":         "claude-haiku-4-5",
    "media_worker":           "claude-sonnet-4-6",
    "audio_worker":           "claude-haiku-4-5",
    "guard_worker":           "claude-haiku-4-5",
    "budget_worker":          "claude-haiku-4-5",
    "digital_product_worker": "claude-sonnet-4-6",
    "marketing_worker":       "claude-sonnet-4-6",
}

MAX_CONCURRENT = 4


def run_task(task: dict) -> dict:
    task_id = task["task_id"]
    role_id = route_task(task)

    if not acquire_lock(task_id, role_id):
        log.info("Task %s already locked — skipping", task_id)
        return {"skipped": True, "task_id": task_id}

    try:
        update_agent_state(role_id, "working", task_id)
        move_task(task_id, "todo", "in_progress")

        model = MODELS.get(role_id, "claude-haiku-4-5")
        agent = AgentBase(role_id, model, build_system_prompt(role_id))
        result = agent.run(task)

        write_task_output(task_id, result["output"], "in_progress")
        move_task(task_id, "in_progress", "done")
        update_agent_state(role_id, "idle", "", f"completed {task_id}")
        log.info("%s completed %s ($%.4f)", role_id, task_id, result["cost_usd"])
        return result

    except Exception as exc:
        log.error("%s failed %s: %s", role_id, task_id, exc)
        try:
            move_task(task_id, "in_progress", "failed")
        except Exception:
            pass
        update_agent_state(role_id, "error", task_id, str(exc))
        return {"error": str(exc), "task_id": task_id}

    finally:
        release_lock(task_id)


def run_cycle() -> None:
    if is_budget_exceeded():
        log.warning("Daily budget cap reached — skipping cycle.")
        return

    tasks = read_todo_tasks()
    if not tasks:
        log.info("No tasks in queue.")
        return

    batch = tasks[:MAX_CONCURRENT]
    log.info("Dispatching %d task(s)", len(batch))

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = [executor.submit(run_task, t) for t in batch]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                log.error("Unhandled task error: %s", exc)


if __name__ == "__main__":
    run_cycle()
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/runner/test_main.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Run the full test suite**

```powershell
python -m pytest tests/ -v
```

Expected: All tests PASSED (no failures).

- [ ] **Step 6: Commit**

```powershell
git add runner\main.py tests\runner\test_main.py
git commit -m "feat: add runner main orchestration loop — Plan 1 complete"
```

---

## Task 12: Dry-Run Smoke Test

Verify the runner works end-to-end against the sample tasks without making real API calls.

- [ ] **Step 1: Set a dummy API key so the SDK initialises**

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-test-key-not-real"
```

- [ ] **Step 2: Run the full test suite one final time**

```powershell
python -m pytest tests/ -v --tb=short
```

Expected: All PASSED. No import errors, no missing module errors.

- [ ] **Step 3: Verify runner imports cleanly**

```powershell
python -c "from runner.main import run_cycle; print('Runner imports OK')"
```

Expected: `Runner imports OK`

- [ ] **Step 4: Check dashboard state file is written by a mocked cycle**

```python
# run this as a one-off script: python scripts/smoke_test_runner.py
from unittest.mock import patch, MagicMock
from runner.main import run_cycle

mock_result = {
    "task_id": "SAMPLE-001",
    "output": "Smoke test output.",
    "cost_usd": 0.0,
    "role_id": "debug_worker",
    "input_tokens": 0,
    "output_tokens": 0,
}

with patch("runner.main.is_budget_exceeded", return_value=False):
    with patch("runner.main.read_todo_tasks", return_value=[{
        "task_id": "SAMPLE-001",
        "task_type": "validation",
        "assigned_agent": "debug_worker",
        "body": "Smoke test.",
        "file_path": "workspace/tasks/todo/SAMPLE-001.md",
    }]):
        with patch("runner.main.acquire_lock", return_value=True):
            with patch("runner.main.release_lock"):
                with patch("runner.main.move_task"):
                    with patch("runner.main.write_task_output"):
                        with patch("runner.main.AgentBase") as MockAgent:
                            MockAgent.return_value.run.return_value = mock_result
                            run_cycle()

import json
from pathlib import Path
state = json.loads(Path("workspace/dashboard-state.json").read_text())
print("State file written OK")
print(f"  Agents: {list(state['agents'].keys())}")
print(f"  Budget: ${state['budget']['spent_usd']} / ${state['budget']['cap_usd']}")
```

Save as `scripts/smoke_test_runner.py`, then run:

```powershell
python scripts\smoke_test_runner.py
```

Expected output:
```
State file written OK
  Agents: ['debug_worker']
  Budget: $0.0 / $50.0
```

- [ ] **Step 5: Final commit**

```powershell
git add scripts\smoke_test_runner.py
git commit -m "test: add smoke test script for runner dry run"
```

---

## What's Next

**Plan 2** builds the 2D dashboard (FastAPI + WebSocket server + HTML/JS frontend) that reads `workspace/dashboard-state.json` and displays all 11 agents in real time.

**Plan 3** wires up the Windows Scheduler, Tony Stocks bridge, image/audio tool adapters, and plugin skill injection.

> **Note on tool adapters:** The `runner/tools/` adapters (`web.py`, `files.py`, `code.py`, `image.py`, `audio.py`) extend AgentBase to support Claude's `tool_use` API — agents make multi-turn calls and invoke tools mid-task. This requires a different execution loop from the single-message pattern in Plan 1. Tool adapters are fully specified and built in Plan 3. The Plan 1 runner works without them: agents receive the task body and respond with text output, which is sufficient for content drafting, analysis, and reporting tasks.

To run the real runner against the sample tasks with a real API key:

```powershell
$env:ANTHROPIC_API_KEY = "your-real-key-here"
python -m runner.main
```
