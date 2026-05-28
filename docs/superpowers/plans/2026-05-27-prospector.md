# Prospector Opportunity-Pod Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Prospector agent (`opportunity_worker`) and `opportunity_pod` — a fully isolated, autonomous pipeline that scouts AI-agent business ideas, scores them, writes specs + samples, builds and grades sandboxed PoCs, and self-tunes nightly — plus shared memory/learning-layer hardening that benefits every agent.

**Architecture:** A new role wired into the existing task-runner exactly like Tony/Pitch (config + MODELS + ROLE_TOOLS + routing). Approach B orchestration: Prospector researches/scores/grades; the existing `heavy_worker` (Forge) builds PoCs. Grading is a separate task type (`poc_grade`) so a future evaluator role is a one-line routing change. Per-pod and per-PoC budget caps are added to the budget ledger. A cross-platform daily hook in `run_cycle()` fixes nightly learning for all agents. Read the approved spec first: `docs/superpowers/specs/2026-05-27-prospector-design.md`.

**Tech Stack:** Python 3.x, OpenAI-compatible function-calling (Gemini direct / OpenRouter), httpx, FastAPI + WebSocket dashboard, pytest, YAML config, Markdown vault files.

---

## File Structure

**New files:**
- `agents/opportunity_worker.md` — Prospector system prompt
- `runner/tools/opportunity.py` — `log_opportunity` + `grade_poc` tools (write to the opportunities ledger / per-opportunity pages)
- `runner/tools/poc_sandbox.py` — `poc_runner` tool: `cwd`-confined PoC command execution
- `runner/scheduler/daily_jobs.py` — cross-platform daily/weekly learning trigger + scout interval trigger (pure logic, state-file driven)
- `scripts/opportunity_synthesis.py` — P4 nightly opportunity learning loop
- `vault/opportunities/ledger.md`, `vault/opportunities/_moc.md` — seed files
- `tests/runner/test_opportunity_tools.py`
- `tests/runner/test_opportunity_routing.py`
- `tests/runner/test_budget_pods.py`
- `tests/runner/test_daily_jobs.py`
- `tests/runner/test_vault_memory_guard.py`
- `tests/runner/test_opportunity_chain.py`
- `tests/runner/test_poc_sandbox.py`
- `tests/runner/test_opportunity_synthesis.py`

**Modified files:**
- `config/agents.yaml` — `opportunity_worker` role + Forge `poc_build`
- `config/budgets.yaml` — `per_pod_limits` + `opportunity_pod`
- `runner/ledger/budget.py` — per-pod spend tracking + caps
- `runner/agents/base.py` — pass `pod` to `record_spend`
- `runner/main.py` — `MODELS`, `TASK_MODEL_OVERRIDES`, `ROLE_TOOLS` (Prospector + Forge additions), pod budget check, daily-job + scout hooks in `run_cycle`
- `runner/agents/prompts.py` — `_ROLE_MD_FILES`
- `runner/tools/task_creator.py` — `VALID_AGENTS` + `opportunity_pod` enum
- `runner/tools/vault_memory.py` — false-success guard hardening
- `scripts/improvement_loop.py` — add `opportunity_worker` to review list
- `agents/librarian.md` — Sage reads Prospector + adds backlinks
- `agents/heavy_worker.md` — Forge PoC-build workflow
- `dashboard/server.py`, `dashboard/index.html` — Opportunity Board panel

**Conventions to follow (from existing code):**
- Tool spec shape: `{"name", "description", "input_schema": {...}}` (Anthropic style; converted to OpenAI by `_to_openai_tools`).
- Tool functions return plain dicts; failures return `{"error": "..."}` and must never raise into the run loop.
- Vault writes use UTF-8; ledger files are Markdown tables; dashboard data is JSON.
- Tests live under `tests/runner/` and run with `pytest`.

---

## PHASE 1 — Scout, Scored Ledger, Board, Budget Caps

### Task 1: Per-pod budget tracking in the ledger

**Files:**
- Modify: `runner/ledger/budget.py`
- Modify: `config/budgets.yaml`
- Test: `tests/runner/test_budget_pods.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_budget_pods.py
import importlib


def _fresh_budget(tmp_path, monkeypatch):
    import runner.ledger.budget as budget
    importlib.reload(budget)
    monkeypatch.setattr(budget, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(budget, "SPEND_FILE", tmp_path / "daily-spend.json")
    return budget


def test_record_spend_tracks_pod(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("opportunity_worker", 1.5, pod="opportunity_pod")
    budget.record_spend("heavy_worker", 0.5, pod="opportunity_pod")
    assert budget.get_pod_spend("opportunity_pod") == 2.0


def test_record_spend_without_pod_is_safe(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    budget.record_spend("outreach_worker", 0.25)
    assert budget.get_pod_spend("opportunity_pod") == 0.0
    assert budget.get_daily_spend() == 0.25


def test_pod_budget_exceeded(tmp_path, monkeypatch):
    budget = _fresh_budget(tmp_path, monkeypatch)
    monkeypatch.setattr(budget, "get_pod_cap", lambda pod: 10.0)
    budget.record_spend("opportunity_worker", 9.99, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is False
    budget.record_spend("opportunity_worker", 0.02, pod="opportunity_pod")
    assert budget.is_pod_budget_exceeded("opportunity_pod") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_budget_pods.py -v`
Expected: FAIL — `record_spend() got an unexpected keyword argument 'pod'` / `AttributeError: get_pod_spend`.

- [ ] **Step 3: Implement per-pod tracking**

Replace the body of `runner/ledger/budget.py` with:

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
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}, "by_pod": {}}
    data = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    if data.get("date") != str(date.today()):
        return {"date": str(date.today()), "total_usd": 0.0, "by_role": {}, "by_pod": {}}
    data.setdefault("by_pod", {})
    return data


def _save_spend(data: dict) -> None:
    SPEND_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_spend(role_id: str, cost_usd: float, pod: str | None = None) -> None:
    data = _load_spend()
    data["total_usd"] = round(data["total_usd"] + cost_usd, 6)
    data["by_role"][role_id] = round(data["by_role"].get(role_id, 0.0) + cost_usd, 6)
    if pod:
        data["by_pod"][pod] = round(data["by_pod"].get(pod, 0.0) + cost_usd, 6)
    _save_spend(data)


def get_daily_spend() -> float:
    return _load_spend()["total_usd"]


def get_pod_spend(pod: str) -> float:
    return _load_spend().get("by_pod", {}).get(pod, 0.0)


def get_daily_cap() -> float:
    from runner.config import load_budgets
    return load_budgets()["budgets"]["daily_limits"]["total_spend_limit_usd"]


def get_pod_cap(pod: str) -> float:
    from runner.config import load_budgets
    limits = load_budgets()["budgets"].get("per_pod_limits", {})
    pod_cfg = limits.get(pod)
    if not pod_cfg:
        return float("inf")
    return float(pod_cfg.get("daily_spend_limit_usd", float("inf")))


def is_budget_exceeded() -> bool:
    return get_daily_spend() >= get_daily_cap()


def is_pod_budget_exceeded(pod: str) -> bool:
    return get_pod_spend(pod) >= get_pod_cap(pod)
```

- [ ] **Step 4: Add the pod cap to config**

In `config/budgets.yaml`, add a `per_pod_limits` block under `budgets:` (after `per_role_limits:`):

```yaml
  per_pod_limits:
    opportunity_pod:
      daily_spend_limit_usd: 10.00
      per_poc_limit_usd: 2.00
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/runner/test_budget_pods.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add runner/ledger/budget.py config/budgets.yaml tests/runner/test_budget_pods.py
git commit -m "feat(budget): per-pod spend tracking and caps"
```

---

### Task 2: Pass pod context into spend recording

**Files:**
- Modify: `runner/agents/base.py` (the `record_spend` call inside `run`)
- Test: append to `tests/runner/test_budget_pods.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/runner/test_budget_pods.py
def test_agentbase_passes_pod(monkeypatch):
    import runner.agents.base as base
    calls = []
    monkeypatch.setattr(base, "record_spend", lambda role, cost, pod=None: calls.append((role, pod)))
    monkeypatch.setattr(base, "dispatch_tool", lambda *a, **k: {})

    agent = base.AgentBase("opportunity_worker", "gemini-2.5-flash", "sys", tools=[])

    class _Msg:
        content = "done"
        tool_calls = None
    class _Choice:
        finish_reason = "stop"
        message = _Msg()
    class _Usage:
        prompt_tokens = 10
        completion_tokens = 5
    class _Resp:
        choices = [_Choice()]
        usage = _Usage()
    monkeypatch.setattr(agent.client.chat.completions, "create", lambda **k: _Resp())

    agent.run({"task_id": "T1", "body": "hi", "pod": "opportunity_pod"})
    assert calls and calls[0][1] == "opportunity_pod"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_budget_pods.py::test_agentbase_passes_pod -v`
Expected: FAIL — pod is `None` (record_spend called without pod).

- [ ] **Step 3: Implement — thread pod through `run`**

In `runner/agents/base.py`, inside `run(self, task)`, locate:

```python
        cost = calculate_cost(self.model, total_input, total_output)
        record_spend(self.role_id, cost)
```

Replace with:

```python
        cost = calculate_cost(self.model, total_input, total_output)
        record_spend(self.role_id, cost, pod=task.get("pod"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runner/test_budget_pods.py::test_agentbase_passes_pod -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runner/agents/base.py tests/runner/test_budget_pods.py
git commit -m "feat(budget): thread pod context into record_spend"
```

---

### Task 3: The `log_opportunity` tool (scored ledger + per-opportunity page)

**Files:**
- Create: `runner/tools/opportunity.py`
- Test: `tests/runner/test_opportunity_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_opportunity_tools.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.opportunity as opp
    importlib.reload(opp)
    monkeypatch.setattr(opp, "OPP_DIR", tmp_path / "opportunities")
    monkeypatch.setattr(opp, "LEDGER_FILE", tmp_path / "opportunities" / "ledger.md")
    return opp


def test_composite_score_math(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    score = opp.composite_score(
        willingness_to_pay=8, revenue_potential=8, problem_severity=8,
        buildability=8, system_fit=8, novelty=8,
    )
    assert score == 80.0


def test_composite_score_weighting(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    score = opp.composite_score(
        willingness_to_pay=10, revenue_potential=0, problem_severity=0,
        buildability=0, system_fit=0, novelty=0,
    )
    assert score == 25.0


def test_log_opportunity_writes_ledger_and_page(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    res = opp.log_opportunity(
        slug="ai-review-reply-agent",
        one_liner="Auto-replies to Google reviews for local businesses",
        problem="SMBs ignore reviews",
        who_pays="MA service businesses",
        willingness_to_pay=8, revenue_potential=7, problem_severity=7,
        buildability=8, system_fit=9, novelty=6,
    )
    assert res["success"] is True
    assert res["composite"] == opp.composite_score(8, 7, 7, 8, 9, 6)
    ledger = opp.LEDGER_FILE.read_text(encoding="utf-8")
    assert "ai-review-reply-agent" in ledger
    assert "| scouted |" in ledger
    page = (opp.OPP_DIR / "ai-review-reply-agent.md").read_text(encoding="utf-8")
    assert "system_fit" in page
    assert "[[ledger]]" in page


def test_log_opportunity_dedup(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    opp.log_opportunity(slug="dup-idea", one_liner="x", problem="p", who_pays="w",
                        willingness_to_pay=5, revenue_potential=5, problem_severity=5,
                        buildability=5, system_fit=5, novelty=5)
    res2 = opp.log_opportunity(slug="dup-idea", one_liner="x", problem="p", who_pays="w",
                               willingness_to_pay=5, revenue_potential=5, problem_severity=5,
                               buildability=5, system_fit=5, novelty=5)
    assert res2.get("skipped") is True
    ledger = opp.LEDGER_FILE.read_text(encoding="utf-8")
    assert ledger.count("| dup-idea |") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_opportunity_tools.py -v`
Expected: FAIL — module `runner.tools.opportunity` not found.

- [ ] **Step 3: Implement `runner/tools/opportunity.py`**

```python
# runner/tools/opportunity.py
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
OPP_DIR = BASE_DIR / "vault" / "opportunities"
LEDGER_FILE = OPP_DIR / "ledger.md"

_WEIGHTS = {
    "willingness_to_pay": 0.25,
    "revenue_potential": 0.20,
    "problem_severity": 0.15,
    "buildability": 0.15,
    "system_fit": 0.15,
    "novelty": 0.10,
}

_LEDGER_HEADER = (
    "# Opportunity Ledger\n\n"
    "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
    "|------|-----------|-------|-----|-----------|-----------|--------|-----|--------|\n"
)


def composite_score(
    willingness_to_pay: float, revenue_potential: float, problem_severity: float,
    buildability: float, system_fit: float, novelty: float,
) -> float:
    dims = {
        "willingness_to_pay": willingness_to_pay,
        "revenue_potential": revenue_potential,
        "problem_severity": problem_severity,
        "buildability": buildability,
        "system_fit": system_fit,
        "novelty": novelty,
    }
    weighted = sum(_WEIGHTS[k] * float(v) for k, v in dims.items())
    return round(weighted * 10, 2)


def _ensure_ledger() -> str:
    OPP_DIR.mkdir(parents=True, exist_ok=True)
    if not LEDGER_FILE.exists():
        LEDGER_FILE.write_text(_LEDGER_HEADER, encoding="utf-8")
    return LEDGER_FILE.read_text(encoding="utf-8")


def _slug_in_ledger(ledger: str, slug: str) -> bool:
    return f"| {slug} |" in ledger


def log_opportunity(
    slug: str, one_liner: str, problem: str, who_pays: str,
    willingness_to_pay: float, revenue_potential: float, problem_severity: float,
    buildability: float, system_fit: float, novelty: float,
    est_rev_mo: float = 0.0,
) -> dict:
    try:
        ledger = _ensure_ledger()
        if _slug_in_ledger(ledger, slug):
            return {"skipped": True, "reason": f"{slug} already in ledger", "slug": slug}

        composite = composite_score(
            willingness_to_pay, revenue_potential, problem_severity,
            buildability, system_fit, novelty,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        row = (
            f"| {slug} | {composite} | scouted | — | {system_fit} | "
            f"{est_rev_mo or '—'} | scouted | — | {today} |\n"
        )
        LEDGER_FILE.write_text(ledger + row, encoding="utf-8")

        page = OPP_DIR / f"{slug}.md"
        page.write_text(
            f"# {slug}\n\n"
            f"> {one_liner}\n\n"
            f"Backlinks: [[ledger]] · [[_moc]]\n\n"
            f"## Scores ({today})\n"
            f"- willingness_to_pay: {willingness_to_pay}\n"
            f"- revenue_potential: {revenue_potential}\n"
            f"- problem_severity: {problem_severity}\n"
            f"- buildability: {buildability}\n"
            f"- system_fit: {system_fit}\n"
            f"- novelty: {novelty}\n"
            f"- **composite: {composite}**\n\n"
            f"## Problem\n{problem}\n\n## Who pays\n{who_pays}\n\n"
            f"## Build Spec\n_pending (P2)_\n\n## Sample Deliverable\n_pending (P2)_\n\n"
            f"## PoC Grade\n_pending (P3)_\n",
            encoding="utf-8",
        )
        return {"success": True, "slug": slug, "composite": composite}
    except OSError as exc:
        return {"error": str(exc)}


TOOL_SPEC_LOG = {
    "name": "log_opportunity",
    "description": (
        "Record a scored AI-agent business opportunity to the opportunity ledger and create its "
        "vault page. Call once per distinct idea you scout. Score each dimension 0-10. The composite "
        "(0-100) is computed for you. Dedupes by slug — never logs the same slug twice."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "kebab-case unique id, e.g. ai-review-reply-agent"},
            "one_liner": {"type": "string", "description": "One-sentence description"},
            "problem": {"type": "string", "description": "The pain this solves"},
            "who_pays": {"type": "string", "description": "Who the paying customer is"},
            "willingness_to_pay": {"type": "number", "description": "0-10: who pays & how much"},
            "revenue_potential": {"type": "number", "description": "0-10: ceiling if it works"},
            "problem_severity": {"type": "number", "description": "0-10: how real/painful"},
            "buildability": {"type": "number", "description": "0-10: inverse of build effort"},
            "system_fit": {"type": "number", "description": "0-10: can THIS system's agents/tools run it"},
            "novelty": {"type": "number", "description": "0-10: non-slop, defensible"},
            "est_rev_mo": {"type": "number", "description": "Estimated monthly revenue in USD (a hypothesis)"},
        },
        "required": [
            "slug", "one_liner", "problem", "who_pays",
            "willingness_to_pay", "revenue_potential", "problem_severity",
            "buildability", "system_fit", "novelty",
        ],
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/runner/test_opportunity_tools.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add runner/tools/opportunity.py tests/runner/test_opportunity_tools.py
git commit -m "feat(opportunity): log_opportunity tool with composite scoring + ledger/page writes"
```

---

### Task 4: Register the role, pod, task types, model tiering, and tools

**Files:**
- Modify: `config/agents.yaml`, `runner/main.py`, `runner/agents/prompts.py`, `runner/tools/task_creator.py`
- Create: `agents/opportunity_worker.md`
- Test: `tests/runner/test_opportunity_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_opportunity_routing.py
import pytest
import runner.tasks.router as r


@pytest.fixture(autouse=True)
def _reset_routing():
    r._routing_table = None
    yield
    r._routing_table = None


def test_scout_routes_to_opportunity_worker():
    assert r.route_task({"task_type": "opportunity_scout"}) == "opportunity_worker"


def test_spec_routes_to_opportunity_worker():
    assert r.route_task({"task_type": "opportunity_spec"}) == "opportunity_worker"


def test_poc_build_routes_to_forge():
    assert r.route_task({"task_type": "poc_build"}) == "heavy_worker"


def test_poc_grade_routes_to_opportunity_worker():
    # C-seam: grading currently routes back to Prospector
    assert r.route_task({"task_type": "poc_grade"}) == "opportunity_worker"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_opportunity_routing.py -v`
Expected: FAIL — task types route to `debug_worker` fallback.

- [ ] **Step 3: Add the role to `config/agents.yaml`**

Append this agent entry to the `agents:` list:

```yaml
  - role_id: opportunity_worker
    display_name: Prospector
    enabled: true
    purpose: Scouts AI-agent business opportunities, scores them, writes specs and samples, and grades sandboxed proof-of-concepts.
    allowed_task_types:
      - opportunity_scout
      - opportunity_deepdive
      - opportunity_spec
      - poc_grade
    forbidden_task_types:
      - direct_publishing
      - real_account_actions
      - budget_override
      - live_trade_execution
    default_model_label: tiered-gemini researcher
    max_retries: 1
    notes: Research + grading role for opportunity_pod. PoC building is delegated to heavy_worker (Forge). Grading (poc_grade) is a swappable seam for a future opportunity_evaluator.
```

> `poc_build` is intentionally NOT in Prospector's allowed_task_types — it is added to `heavy_worker`'s list in Step 4.

- [ ] **Step 4: Give Forge the `poc_build` task type**

In `config/agents.yaml`, under the existing `heavy_worker` agent's `allowed_task_types:`, add one line:

```yaml
      - poc_build
```

- [ ] **Step 5: Wire MODELS, overrides, ROLE_TOOLS in `runner/main.py`**

Add this import near the other tool imports:

```python
from runner.tools.opportunity import TOOL_SPEC_LOG as OPP_LOG_TOOL_SPEC
from runner.tools.code import TOOL_SPEC as CODE_TOOL_SPEC
```

In the `MODELS` dict, add:

```python
    "opportunity_worker":     "gemini-2.5-flash",   # Prospector — scout default; deep-dive overridden to Pro
```

Add a config-driven per-task model map to `config/agents.yaml` as a NEW top-level key (sibling of `agents:`), so the cheapest viable model for each phase is applied automatically every run and is tunable in one place:

```yaml
# Efficient model per phase — auto-applied by run_task on every task.
# Cheapest model that does each job well. Tune here; no code change needed.
task_models:
  opportunity_scout:    gemini-2.5-flash       # bulk idea generation + first-pass scoring
  opportunity_deepdive: gemini-2.5-pro          # the one place depth pays off (top candidates only)
  opportunity_spec:     gemini-2.5-flash        # drafting from already-researched deep-dive
  poc_grade:            gemini-2.5-flash        # structured verdict vs. the spec
  # poc_build is routed to heavy_worker (Forge); its model stays the role default (kimi-k2.5)
```

Immediately AFTER the `MODELS` dict in `runner/main.py`, load that map (config-driven so it auto-switches per phase every run and the operator can tune efficiency without touching code):

```python
def _load_task_models() -> dict[str, str]:
    """Per-task-type model overrides from config/agents.yaml `task_models:`.
    Lets every phase auto-use its most efficient model, tunable without code changes."""
    from runner.config import load_agents
    return load_agents().get("task_models", {}) or {}

# Resolved once at import; restart the runner to pick up config edits.
TASK_MODEL_OVERRIDES: dict[str, str] = _load_task_models()
```

In the `ROLE_TOOLS` dict, add Prospector and extend Forge. Add:

```python
    "opportunity_worker":     [WEB_TOOL_SPEC, FILE_TOOL_SPEC, OPP_LOG_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
```

Change the existing `heavy_worker` line from:

```python
    "heavy_worker":           [FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],
```
to:
```python
    "heavy_worker":           [FILE_TOOL_SPEC, CODE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
```

In `run_task`, change the model selection line from:

```python
        model = MODELS.get(role_id, "gemini-2.5-flash-lite")
```
to:
```python
        model = TASK_MODEL_OVERRIDES.get(task.get("task_type")) or MODELS.get(role_id, "gemini-2.5-flash-lite")
```

- [ ] **Step 6: Register the prompt file in `runner/agents/prompts.py`**

In `_ROLE_MD_FILES`, add:

```python
    "opportunity_worker":     "agents/opportunity_worker.md",
```

- [ ] **Step 7: Allow the agent + pod in `runner/tools/task_creator.py`**

Add `"opportunity_worker"` to `VALID_AGENTS`. Add `"opportunity_pod"` to the `pod` enum in `TOOL_SPEC["input_schema"]["properties"]["pod"]["enum"]`.

- [ ] **Step 8: Create `agents/opportunity_worker.md`**

```markdown
# Prospector — Opportunity Worker

You are Prospector. You hunt real AI-agent business opportunities, score them honestly, and prove the best ones out. You are research + grading only — you never build PoC code yourself (Forge does that) and you never take real external actions.

## What counts as a good opportunity
- A specific painful problem with an identifiable paying customer (not "an app for X").
- Buildable with AI agents/tools. Bonus if THIS system could run it (see system_fit).
- Non-slop: not a me-too wrapper. Defensible angle.

## Scout workflow (task_type: opportunity_scout)
1. Read `vault/opportunities/ledger.md` FIRST (file_editor action=read). Note slugs already present — never re-scout them.
2. Web-research current AI-agent business ideas, niches, and pain points (web_research action=search). Aim for 15-20 candidate ideas.
3. For each NEW idea, score six dimensions 0-10 and call `log_opportunity`:
   - willingness_to_pay, revenue_potential, problem_severity, buildability, system_fit, novelty
   - system_fit = how well THIS system's existing agents/tools (web research, site builder Clay, outreach Pitch, content) could actually run it. High = reuses what we have.
4. For every idea scoring composite >= 75, call `create_task` to spawn an `opportunity_deepdive` task (assigned_agent=opportunity_worker, pod=opportunity_pod) for that slug.
5. Call `write_memory` (entry_type=metric) with how many ideas scouted and how many >=75.

## Deep-dive + spec workflow (task_type: opportunity_deepdive / opportunity_spec)
1. Read the opportunity's page `vault/opportunities/<slug>.md`.
2. Deep web-research the idea: market size, competitors, who pays, pricing.
3. Re-score honestly with evidence (you may revise the scores down).
4. Append a Build Spec to the page (file_editor action=append): inputs, outputs, which existing tools/agents it reuses, estimated cost-per-run, and a hand-written SAMPLE deliverable.
5. If the re-scored composite is still >= 75, call `create_task` to spawn a `poc_build` task (assigned_agent=heavy_worker, pod=opportunity_pod) describing exactly what the PoC must demonstrate and the fixture input to use.

## Grade workflow (task_type: poc_grade)
1. Read the PoC output captured under `workspace/poc/<slug>/`.
2. Compare it to the Build Spec's expected output shape.
3. Call `grade_poc` with verdict promising/weak/dead and a one-paragraph reason.

## Hard rules
- Never invent market data. Cite what web_research returned.
- Never take real external actions (no sends, no signups, no deploys).
- Use the function-calling interface for EVERY tool. NEVER write tool calls as text/XML.
- Format opportunity slugs as `[[slug]]` wikilinks in your output.
```

- [ ] **Step 9: Run routing tests**

Run: `pytest tests/runner/test_opportunity_routing.py -v`
Expected: PASS (4 passed).

- [ ] **Step 10: Commit**

```bash
git add config/agents.yaml runner/main.py runner/agents/prompts.py runner/tools/task_creator.py agents/opportunity_worker.md tests/runner/test_opportunity_routing.py
git commit -m "feat(opportunity): register Prospector role, pod task types, model tiering, Forge poc_build"
```

---

### Task 5: Pod budget enforcement in the run loop

**Files:**
- Modify: `runner/main.py` (`run_task`)
- Test: append to `tests/runner/test_budget_pods.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/runner/test_budget_pods.py
def test_run_task_skips_when_pod_budget_exceeded(monkeypatch):
    import runner.main as main
    monkeypatch.setattr(main, "route_task", lambda t: "opportunity_worker")
    monkeypatch.setattr(main, "acquire_lock", lambda *a: True)
    monkeypatch.setattr(main, "release_lock", lambda *a: None)
    monkeypatch.setattr(main, "is_budget_exceeded", lambda: False)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: True)
    called = {"ran": False}
    def _should_not_run(*a, **k):
        called["ran"] = True
    monkeypatch.setattr(main, "move_task", _should_not_run)

    result = main.run_task({"task_id": "T1", "pod": "opportunity_pod"})
    assert result.get("skipped") is True
    assert called["ran"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_budget_pods.py::test_run_task_skips_when_pod_budget_exceeded -v`
Expected: FAIL — `is_pod_budget_exceeded` not imported in main; task proceeds.

- [ ] **Step 3: Implement the pod check**

In `runner/main.py`, update the budget import line:

```python
from runner.ledger.budget import is_budget_exceeded, is_pod_budget_exceeded
```

In `run_task`, right after the existing global budget check block (the one that returns `{"skipped": True, "task_id": task_id}`), add:

```python
    pod = task.get("pod")
    if pod and is_pod_budget_exceeded(pod):
        release_lock(task_id)
        log.warning("Pod budget cap reached for %s — skipping %s", pod, task_id)
        return {"skipped": True, "task_id": task_id, "reason": f"{pod} daily cap reached"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/runner/test_budget_pods.py::test_run_task_skips_when_pod_budget_exceeded -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runner/main.py tests/runner/test_budget_pods.py
git commit -m "feat(budget): enforce per-pod daily cap in run_task"
```

---

### Task 6: Seed the vault + Opportunity Board dashboard panel

**Files:**
- Create: `vault/opportunities/ledger.md`, `vault/opportunities/_moc.md`
- Modify: `dashboard/server.py`, `dashboard/index.html`

- [ ] **Step 1: Seed the vault files**

`vault/opportunities/ledger.md`:

```markdown
# Opportunity Ledger

| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |
|------|-----------|-------|-----|-----------|-----------|--------|-----|--------|
```

`vault/opportunities/_moc.md`:

```markdown
# Opportunities — Map of Content

#agent-memory #opportunities

The opportunity discovery knowledge hub. See [[ledger]] for the live scored table.

## Pages
_New opportunity pages link back here automatically as Prospector scouts them._
```

- [ ] **Step 2: Add the data source in `dashboard/server.py`**

First READ `dashboard/server.py` to find the function that builds the WebSocket/state payload (look for where it reads task folders / agent state and returns a dict that is broadcast). Add these helpers near the other vault-reading helpers:

```python
def read_opportunities() -> list[dict]:
    """Parse vault/opportunities/ledger.md into rows for the Opportunity Board."""
    from pathlib import Path
    ledger = Path(__file__).parent.parent / "vault" / "opportunities" / "ledger.md"
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
```

Then in the state-payload dict (the one broadcast over the WebSocket), add:

```python
        "opportunities": read_opportunities(),
        "opportunity_spend": read_pod_spend(),
```

- [ ] **Step 3: Add the panel to `dashboard/index.html`**

Add a new `.panel` block where the right-column panels live, using the existing CSS variables:

```html
<div class="panel" id="opportunity-board">
  <div class="panel-title">OPPORTUNITY BOARD</div>
  <div class="opp-vitals">
    <span id="opp-spend">$0 / $10</span>
    <span id="opp-count">0 ideas</span>
    <span id="opp-promising">0 promising</span>
  </div>
  <table class="opp-table">
    <thead><tr><th>#</th><th>idea</th><th>score</th><th>phase</th><th>poc</th><th>fit</th><th>$est</th></tr></thead>
    <tbody id="opp-rows"></tbody>
  </table>
</div>
```

Add this render function in the page script and call `renderOpportunities(data)` inside the existing WebSocket `onmessage` handler alongside the other render calls:

```javascript
function renderOpportunities(data) {
  const s = data.opportunity_spend || {spent: 0, cap: 10};
  document.getElementById('opp-spend').textContent = `$${s.spent} / $${s.cap}`;
  const rows = data.opportunities || [];
  document.getElementById('opp-count').textContent = `${rows.length} ideas`;
  const promising = rows.filter(r => (r.poc || '').includes('promis')).length;
  document.getElementById('opp-promising').textContent = `${promising} promising`;
  const tbody = document.getElementById('opp-rows');
  tbody.innerHTML = '';
  rows.forEach((r, i) => {
    const score = parseFloat(r.composite) || 0;
    const color = score >= 75 ? 'var(--green)' : (score >= 60 ? 'var(--orange)' : 'var(--muted)');
    const tr = document.createElement('tr');
    tr.innerHTML =
      `<td>${i + 1}</td><td>${r.slug}</td>` +
      `<td style="color:${color}">${r.composite}</td>` +
      `<td>${r.phase}</td><td>${r.poc}</td><td>${r.system_fit}</td><td>${r.est_rev_mo}</td>`;
    tbody.appendChild(tr);
  });
}
```

Add minimal CSS reusing the variables:

```css
.opp-vitals { display:flex; gap:12px; font-size:11px; color:var(--muted); padding:6px 10px; }
.opp-table { width:100%; border-collapse:collapse; font-size:11px; }
.opp-table th { color:var(--muted); text-align:left; font-weight:normal; padding:4px 6px; }
.opp-table td { padding:4px 6px; border-top:1px solid var(--border); color:var(--text); }
```

- [ ] **Step 4: Manual verification**

Run: `python scripts/launch.py --once`
Open `http://127.0.0.1:8765`. Confirm the OPPORTUNITY BOARD panel renders (empty table is fine), no console errors, and the rest of the dashboard is unchanged.

- [ ] **Step 5: Commit**

```bash
git add vault/opportunities/ledger.md vault/opportunities/_moc.md dashboard/server.py dashboard/index.html
git commit -m "feat(dashboard): Opportunity Board panel + ledger/spend data source"
```

---

### Task 7: Scout interval trigger (isolated from Atlas)

**Files:**
- Create: `runner/scheduler/daily_jobs.py`
- Modify: `runner/main.py` (`run_cycle`)
- Test: `tests/runner/test_daily_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_daily_jobs.py
import importlib
from datetime import datetime, timedelta


def _fresh(tmp_path, monkeypatch):
    import runner.scheduler.daily_jobs as dj
    importlib.reload(dj)
    monkeypatch.setattr(dj, "STATE_FILE", tmp_path / "scheduler-state.json")
    return dj


def test_scout_due_when_never_run(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    assert dj.scout_due(interval_hours=2) is True


def test_scout_not_due_within_interval(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    dj.mark_scout_ran()
    assert dj.scout_due(interval_hours=2) is False


def test_scout_due_after_interval(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    dj.mark_scout_ran()
    old = (datetime.now() - timedelta(hours=3)).isoformat()
    dj._write({"last_scout": old})
    assert dj.scout_due(interval_hours=2) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/runner/test_daily_jobs.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `runner/scheduler/daily_jobs.py`**

```python
# runner/scheduler/daily_jobs.py
import json
from datetime import datetime, date
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent.parent / "workspace" / "scheduler-state.json"


def _read() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def scout_due(interval_hours: float = 2.0) -> bool:
    last = _read().get("last_scout")
    if not last:
        return True
    try:
        elapsed = datetime.now() - datetime.fromisoformat(last)
    except ValueError:
        return True
    return elapsed.total_seconds() >= interval_hours * 3600


def mark_scout_ran() -> None:
    data = _read()
    data["last_scout"] = datetime.now().isoformat()
    _write(data)


def daily_learning_due(hour_after: int = 2) -> bool:
    """True once per day, only after the given hour (local)."""
    data = _read()
    today = str(date.today())
    if data.get("last_learning_date") == today:
        return False
    return datetime.now().hour >= hour_after


def mark_learning_ran() -> None:
    data = _read()
    data["last_learning_date"] = str(date.today())
    _write(data)


def weekly_sage_due() -> bool:
    """True once on Sundays (weekday 6) if not already run today."""
    data = _read()
    today = str(date.today())
    if datetime.now().weekday() != 6:
        return False
    return data.get("last_sage_date") != today


def mark_sage_ran() -> None:
    data = _read()
    data["last_sage_date"] = str(date.today())
    _write(data)
```

- [ ] **Step 4: Wire the scout trigger into `run_cycle`**

In `runner/main.py`, add import:

```python
from runner.scheduler.daily_jobs import scout_due, mark_scout_ran
```

Add a helper near `_maybe_spawn_planning_task`:

```python
_SCOUT_TASK_BODY = """\
Run the Prospector opportunity scout for opportunity_pod.

1. Read vault/opportunities/ledger.md first — skip slugs already present.
2. Web-research current AI-agent business ideas. Produce 15-20 candidates.
3. Score each new idea (six dimensions 0-10) and call log_opportunity.
4. For each idea with composite >= 75, create an opportunity_deepdive task (opportunity_worker, opportunity_pod).
5. write_memory(entry_type=metric) with counts scouted / >=75.
"""


def _maybe_spawn_scout() -> None:
    if not scout_due(interval_hours=2):
        return
    from runner.tools.task_creator import create_task
    if is_pod_budget_exceeded("opportunity_pod"):
        return
    result = create_task(
        title="Prospector: Opportunity Scout",
        body=_SCOUT_TASK_BODY,
        assigned_agent="opportunity_worker",
        task_type="opportunity_scout",
        pod="opportunity_pod",
        priority="low",
    )
    if result.get("success") or result.get("skipped"):
        mark_scout_ran()
    log.info("Scout trigger: %s", result.get("task_id", result))
```

In `run_cycle`, after the existing `_maybe_spawn_planning_task()` call near the end, add:

```python
    _maybe_spawn_scout()
```

> Isolation guarantee: this is a SEPARATE function from `_maybe_spawn_planning_task` (Atlas). It only ever creates `opportunity_scout` tasks and never touches Pitch/Tony logic.

- [ ] **Step 5: Run tests**

Run: `pytest tests/runner/test_daily_jobs.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add runner/scheduler/daily_jobs.py runner/main.py tests/runner/test_daily_jobs.py
git commit -m "feat(scheduler): isolated Prospector scout interval trigger"
```

---

## SHARED LEARNING-LAYER HARDENING

### Task 8: Cross-platform nightly learning hook

**Files:**
- Modify: `runner/main.py` (`run_cycle`)
- Test: extend `tests/runner/test_daily_jobs.py`

- [ ] **Step 1: Write the test**

```python
# append to tests/runner/test_daily_jobs.py
def test_daily_learning_runs_once_per_day(tmp_path, monkeypatch):
    dj = _fresh(tmp_path, monkeypatch)
    if dj.datetime.now().hour < 2:
        return  # before 2am the gate is intentionally closed; skip
    assert dj.daily_learning_due(hour_after=2) is True
    dj.mark_learning_ran()
    assert dj.daily_learning_due(hour_after=2) is False
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_daily_jobs.py::test_daily_learning_runs_once_per_day -v`
Expected: PASS (functions already exist from Task 7).

- [ ] **Step 3: Wire the learning hook into `run_cycle`**

In `runner/main.py`, replace the Task 7 import with the fuller import:

```python
from runner.scheduler.daily_jobs import (
    scout_due, mark_scout_ran,
    daily_learning_due, mark_learning_ran,
    weekly_sage_due, mark_sage_ran,
)
```

Add a helper:

```python
def _maybe_run_learning() -> None:
    if not daily_learning_due(hour_after=2):
        return
    import subprocess
    root = Path(__file__).parent.parent
    log.info("Daily learning hook firing — improvement_loop + opportunity_synthesis")
    subprocess.run([sys.executable, str(root / "scripts" / "improvement_loop.py")], cwd=root, check=False)
    syn = root / "scripts" / "opportunity_synthesis.py"
    if syn.exists():
        subprocess.run([sys.executable, str(syn)], cwd=root, check=False)
    if weekly_sage_due():
        from runner.tools.task_creator import create_task
        create_task(
            title="Sage: Weekly Memory Synthesis",
            body="Run the full librarian synthesis workflow across all agent memory logs.",
            assigned_agent="librarian", task_type="memory_synthesis",
            pod="management", priority="low",
        )
        mark_sage_ran()
    mark_learning_ran()
```

In `run_cycle`, after `_maybe_spawn_scout()`, add:

```python
    _maybe_run_learning()
```

- [ ] **Step 4: Manual smoke test**

Run: `python -c "from runner.scheduler.daily_jobs import daily_learning_due; print(daily_learning_due())"`
Expected: prints `True` or `False` without error.

- [ ] **Step 5: Commit**

```bash
git add runner/main.py tests/runner/test_daily_jobs.py
git commit -m "feat(learning): cross-platform daily learning hook in run_cycle"
```

---

### Task 9: False-success / errored-run guard in vault memory

**Files:**
- Modify: `runner/tools/vault_memory.py` (`auto_write_task_memory`)
- Test: `tests/runner/test_vault_memory_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_vault_memory_guard.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.vault_memory as vm
    importlib.reload(vm)
    monkeypatch.setattr(vm, "AGENTS_MEMORY_DIR", tmp_path / "agents")
    return vm


def test_no_tool_call_run_logged_as_noop(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    vm.auto_write_task_memory("x_worker", "T1", "scan", "success", "(no tool calls made this run)")
    text = (vm.AGENTS_MEMORY_DIR / "x_worker" / "memory.md").read_text(encoding="utf-8")
    assert "noop" in text


def test_errored_run_logged_as_failure(tmp_path, monkeypatch):
    vm = _fresh(tmp_path, monkeypatch)
    vm.auto_write_task_memory("x_worker", "T2", "scan", "success",
                              "Run completed via tool calls: web_research. ALL_TOOLS_ERRORED")
    text = (vm.AGENTS_MEMORY_DIR / "x_worker" / "memory.md").read_text(encoding="utf-8")
    assert "failure" in text
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_vault_memory_guard.py -v`
Expected: FAIL on `test_errored_run_logged_as_failure`.

- [ ] **Step 3: Extend the guard**

In `runner/tools/vault_memory.py`, inside `auto_write_task_memory`, find:

```python
        if outcome == "success" and "(no tool calls made this run)" in (summary or ""):
            outcome = "noop"
```

Add immediately after it:

```python
        if outcome == "success" and "ALL_TOOLS_ERRORED" in (summary or ""):
            outcome = "failure"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/runner/test_vault_memory_guard.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add runner/tools/vault_memory.py tests/runner/test_vault_memory_guard.py
git commit -m "fix(memory): downgrade all-errored runs to failure, not success"
```

---

### Task 10: Add Prospector to improvement loop + Sage

**Files:**
- Modify: `scripts/improvement_loop.py`, `agents/librarian.md`

- [ ] **Step 1: Add Prospector to the review list**

In `scripts/improvement_loop.py`, change `_AGENTS_TO_REVIEW` to:

```python
_AGENTS_TO_REVIEW = [
    "manager",
    "outreach_worker",
    "market_research_worker",
    "opportunity_worker",
]
```

- [ ] **Step 2: Add Prospector to Sage's read list + backlinks**

In `agents/librarian.md`, add to the "Files to read" list in Step 1:

```markdown
- `vault/agents/opportunity_worker/memory.md`
```

Add a bullet to the Step 2 rules:

```markdown
- When distilling rules that reference an entity (a ticker, a CRM contact, an opportunity slug), add an Obsidian backlink to it in the rule line, e.g. `[[ai-review-reply-agent]]`, so the graph connects learned rules to the entities they describe.
```

- [ ] **Step 3: Verify the improvement loop still parses**

Run: `python -c "import ast; ast.parse(open('scripts/improvement_loop.py').read()); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add scripts/improvement_loop.py agents/librarian.md
git commit -m "feat(learning): include Prospector in nightly loop + Sage synthesis with graph backlinks"
```

---

## PHASE 2 — Deep-dive, Build Spec, Sample (no code execution)

Phase 2 needs no new code — it is driven by the `opportunity_worker.md` prompt (Task 4 Step 8 already includes the deep-dive/spec workflow), the Pro model override (Task 4 Step 5), and the auto-chaining `create_task` calls. Phase 2 is therefore verification.

### Task 11: Verify the P2 chain (mocked)

**Files:**
- Test: `tests/runner/test_opportunity_chain.py`

- [ ] **Step 1: Write the test**

```python
# tests/runner/test_opportunity_chain.py
import importlib


def test_spec_append_and_promotion_threshold(tmp_path, monkeypatch):
    import runner.tools.opportunity as opp
    importlib.reload(opp)
    monkeypatch.setattr(opp, "OPP_DIR", tmp_path / "opportunities")
    monkeypatch.setattr(opp, "LEDGER_FILE", tmp_path / "opportunities" / "ledger.md")
    opp.log_opportunity(slug="svc", one_liner="x", problem="p", who_pays="w",
                        willingness_to_pay=9, revenue_potential=8, problem_severity=8,
                        buildability=8, system_fit=8, novelty=7)
    page = opp.OPP_DIR / "svc.md"
    assert "_pending (P2)_" in page.read_text(encoding="utf-8")
    page.write_text(page.read_text(encoding="utf-8").replace(
        "## Build Spec\n_pending (P2)_", "## Build Spec\nInputs: review text. Output: reply draft."
    ), encoding="utf-8")
    assert "reply draft" in page.read_text(encoding="utf-8")
    assert opp.composite_score(9, 8, 8, 8, 8, 7) >= 75
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_opportunity_chain.py -v`
Expected: PASS.

- [ ] **Step 3: Manual integration check (optional, real API cost)**

```bash
python -c "from runner.tools.task_creator import create_task; print(create_task(title='Prospector scout', body='Scout 5 AI-agent ideas, score, log_opportunity each, spawn deepdive for >=75.', assigned_agent='opportunity_worker', task_type='opportunity_scout', pod='opportunity_pod'))"
python scripts/launch.py --once
```

Expected: `vault/opportunities/ledger.md` gains rows; any score ≥75 produces an `opportunity_deepdive` task in `workspace/tasks/todo/`; `workspace/ledger/daily-spend.json` shows `by_pod.opportunity_pod` > 0 and < 10.

- [ ] **Step 4: Commit**

```bash
git add tests/runner/test_opportunity_chain.py
git commit -m "test(opportunity): P2 spec append + promotion threshold"
```

---

## PHASE 3 — Sandboxed PoC Build + Grade

### Task 12: The `poc_runner` sandbox tool (cwd-confined, metered)

**Files:**
- Create: `runner/tools/poc_sandbox.py`
- Modify: `runner/main.py` (give Forge the tool)
- Test: `tests/runner/test_poc_sandbox.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_poc_sandbox.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import runner.tools.poc_sandbox as ps
    importlib.reload(ps)
    monkeypatch.setattr(ps, "POC_ROOT", tmp_path / "poc")
    return ps


def test_rejects_slug_escape(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="../evil", command="echo hi")
    assert res.get("blocked") is True


def test_runs_in_slug_dir(tmp_path, monkeypatch):
    ps = _fresh(tmp_path, monkeypatch)
    res = ps.poc_runner(slug="demo", command="echo prospector-ok")
    assert "prospector-ok" in (res.get("stdout") or "")
    assert (ps.POC_ROOT / "demo").exists()
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_poc_sandbox.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `runner/tools/poc_sandbox.py`**

```python
# runner/tools/poc_sandbox.py
import re
import subprocess
from pathlib import Path

from runner.tools.code import _is_forbidden

POC_ROOT = Path(__file__).parent.parent.parent / "workspace" / "poc"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


def _safe_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug)) and ".." not in slug


def poc_runner(slug: str, command: str, timeout: int = 30) -> dict:
    if not _safe_slug(slug):
        return {"blocked": True, "error": f"Invalid slug: {slug!r}"}
    if _is_forbidden(command):
        return {"blocked": True, "error": "Command blocked by safety filter"}
    workdir = POC_ROOT / slug
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout, cwd=str(workdir),
        )
        return {
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:4000],
            "exit_code": result.returncode,
            "workdir": str(workdir),
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": "timeout exceeded"}
    except OSError as exc:
        return {"stdout": "", "stderr": "", "exit_code": -1, "error": str(exc)}


TOOL_SPEC = {
    "name": "poc_runner",
    "description": (
        "Run a PowerShell command for a proof-of-concept, confined to workspace/poc/<slug>/. "
        "Use this (not code_runner) to scaffold and run PoC demos. The working directory is the slug "
        "folder; write files there with relative paths. No directory escape. Subprocess timeout enforced."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Opportunity slug — the PoC folder name"},
            "command": {"type": "string", "description": "PowerShell command (runs with cwd = the slug folder)"},
            "timeout": {"type": "integer", "description": "Timeout seconds (default 30)", "default": 30},
        },
        "required": ["slug", "command"],
    },
}
```

> Network isolation note: true network blocking on Windows is out of scope; the PoC is bounded instead by (a) the per-PoC/pod budget cap, (b) the forbidden-pattern filter, (c) cwd confinement, and (d) the prompt forbidding real external sends/signups/deploys.

- [ ] **Step 4: Run tests**

Run: `pytest tests/runner/test_poc_sandbox.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Give Forge the poc_runner tool**

In `runner/main.py`, add `from runner.tools.poc_sandbox import TOOL_SPEC as POC_RUNNER_TOOL_SPEC` and update the `heavy_worker` ROLE_TOOLS line to:

```python
    "heavy_worker":           [FILE_TOOL_SPEC, CODE_TOOL_SPEC, POC_RUNNER_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
```

- [ ] **Step 6: Commit**

```bash
git add runner/tools/poc_sandbox.py tests/runner/test_poc_sandbox.py runner/main.py
git commit -m "feat(poc): cwd-confined PoC sandbox runner tool for Forge"
```

---

### Task 13: The `grade_poc` tool + Forge build prompt

**Files:**
- Modify: `runner/tools/opportunity.py` (add `grade_poc` + `TOOL_SPEC_GRADE`)
- Modify: `runner/main.py` (add `OPP_GRADE_TOOL_SPEC` to Prospector tools)
- Modify/Create: `agents/heavy_worker.md`
- Test: extend `tests/runner/test_opportunity_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/runner/test_opportunity_tools.py
def test_grade_poc_updates_ledger_and_page(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    opp.log_opportunity(slug="g1", one_liner="x", problem="p", who_pays="w",
                        willingness_to_pay=8, revenue_potential=8, problem_severity=8,
                        buildability=8, system_fit=8, novelty=8)
    res = opp.grade_poc(slug="g1", verdict="promising", reason="Demo produced correct reply drafts.")
    assert res["success"] is True
    ledger = opp.LEDGER_FILE.read_text(encoding="utf-8")
    assert "| g1 |" in ledger and "promis" in ledger
    page = (opp.OPP_DIR / "g1.md").read_text(encoding="utf-8")
    assert "promising" in page and "correct reply drafts" in page


def test_grade_poc_rejects_unknown_verdict(tmp_path, monkeypatch):
    opp = _fresh(tmp_path, monkeypatch)
    res = opp.grade_poc(slug="g2", verdict="awesome", reason="x")
    assert res.get("error")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_opportunity_tools.py::test_grade_poc_updates_ledger_and_page -v`
Expected: FAIL — `grade_poc` not defined.

- [ ] **Step 3: Implement `grade_poc` in `runner/tools/opportunity.py`**

Append to `runner/tools/opportunity.py`:

```python
_VALID_VERDICTS = {"promising", "weak", "dead"}


def grade_poc(slug: str, verdict: str, reason: str) -> dict:
    if verdict not in _VALID_VERDICTS:
        return {"error": f"verdict must be one of {sorted(_VALID_VERDICTS)}"}
    try:
        page = OPP_DIR / f"{slug}.md"
        if page.exists():
            text = page.read_text(encoding="utf-8")
            today = datetime.now().strftime("%Y-%m-%d")
            graded = text.replace(
                "## PoC Grade\n_pending (P3)_",
                f"## PoC Grade\n**{verdict}** ({today}) — {reason}",
            )
            if graded == text:  # already graded before; append
                graded = text + f"\n\n## PoC Grade ({today})\n**{verdict}** — {reason}\n"
            page.write_text(graded, encoding="utf-8")
        if LEDGER_FILE.exists():
            lines = LEDGER_FILE.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if line.startswith(f"| {slug} |"):
                    cells = [c.strip() for c in line.strip("|").split("|")]
                    if len(cells) >= 9:
                        cells[2] = "graded"   # phase
                        cells[3] = verdict     # poc
                        cells[6] = "graded"    # status
                        cells[8] = datetime.now().strftime("%Y-%m-%d")
                        lines[i] = "| " + " | ".join(cells) + " |"
                    break
            LEDGER_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"success": True, "slug": slug, "verdict": verdict}
    except OSError as exc:
        return {"error": str(exc)}


TOOL_SPEC_GRADE = {
    "name": "grade_poc",
    "description": (
        "Grade a proof-of-concept after reviewing its output under workspace/poc/<slug>/. "
        "verdict: promising = demo works and is worth scaling; weak = partial/unconvincing; "
        "dead = failed or no path. Updates the ledger and the opportunity page."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "slug": {"type": "string"},
            "verdict": {"type": "string", "enum": ["promising", "weak", "dead"]},
            "reason": {"type": "string", "description": "One paragraph justifying the verdict, citing the PoC output."},
        },
        "required": ["slug", "verdict", "reason"],
    },
}
```

- [ ] **Step 4: Add `grade_poc` to Prospector's tools**

In `runner/main.py`, change the opportunity import to:

```python
from runner.tools.opportunity import TOOL_SPEC_LOG as OPP_LOG_TOOL_SPEC, TOOL_SPEC_GRADE as OPP_GRADE_TOOL_SPEC
```

Update Prospector's ROLE_TOOLS line to:

```python
    "opportunity_worker":     [WEB_TOOL_SPEC, FILE_TOOL_SPEC, OPP_LOG_TOOL_SPEC, OPP_GRADE_TOOL_SPEC, TASK_CREATOR_TOOL_SPEC, MEMORY_TOOL_SPEC],
```

- [ ] **Step 5: Add the PoC-build section to `agents/heavy_worker.md`**

If `agents/heavy_worker.md` does not exist, create it with a one-line role intro first. Append:

```markdown
## PoC Build workflow (task_type: poc_build)

You are building a sandboxed proof-of-concept for an opportunity. The task body names the `<slug>`, what the PoC must demonstrate, and the fixture input.

1. Use `poc_runner` (NOT code_runner) for all commands — it confines you to `workspace/poc/<slug>/`.
2. Write demo files with `file_editor` under `workspace/poc/<slug>/` (relative paths).
3. Create the fixture input file described in the task, run the demo once with `poc_runner` against it, and capture output to `workspace/poc/<slug>/output.txt`.
4. You MAY use existing tools (web_research, etc.) but stay within the per-PoC budget — a handful of calls max.
5. NEVER perform real external actions: no real sends, no account signups, no deploys.
6. End by calling `create_task` to spawn a `poc_grade` task (assigned_agent=opportunity_worker, pod=opportunity_pod) referencing the slug and the captured output path.
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/runner/test_opportunity_tools.py -v`
Expected: PASS (all).

- [ ] **Step 7: Commit**

```bash
git add runner/tools/opportunity.py runner/main.py agents/heavy_worker.md tests/runner/test_opportunity_tools.py
git commit -m "feat(poc): grade_poc tool + Forge PoC-build workflow (C-seam grading)"
```

---

## PHASE 4 — Nightly Opportunity Synthesis (self-tuning)

### Task 14: `opportunity_synthesis.py` — score-vs-demo divergence learning

**Files:**
- Create: `scripts/opportunity_synthesis.py`
- Test: `tests/runner/test_opportunity_synthesis.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/runner/test_opportunity_synthesis.py
import importlib


def _fresh(tmp_path, monkeypatch):
    import scripts.opportunity_synthesis as syn
    importlib.reload(syn)
    monkeypatch.setattr(syn, "LEDGER_FILE", tmp_path / "ledger.md")
    monkeypatch.setattr(syn, "LEARNINGS_DIR", tmp_path / "learnings")
    return syn


def test_divergence_detects_high_score_dead(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        "# Opportunity Ledger\n\n"
        "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| a | 82 | graded | dead | 9 | 900 | graded | — | 2026-05-27 |\n"
        "| b | 80 | graded | promising | 8 | 800 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    diverging = syn.find_divergence(threshold=75)
    assert any(rr["slug"] == "a" for rr in diverging)
    assert all(rr["slug"] != "b" for rr in diverging)


def test_writes_learnings_note(tmp_path, monkeypatch):
    syn = _fresh(tmp_path, monkeypatch)
    syn.LEDGER_FILE.write_text(
        "# Opportunity Ledger\n\n"
        "| slug | composite | phase | poc | system_fit | est_rev_mo | status | pod | updated |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| a | 82 | graded | dead | 9 | 900 | graded | — | 2026-05-27 |\n",
        encoding="utf-8",
    )
    syn.write_learnings(syn.find_divergence(75))
    notes = list((syn.LEARNINGS_DIR).glob("*-opportunities.md"))
    assert notes and "a" in notes[0].read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test**

Run: `pytest tests/runner/test_opportunity_synthesis.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `scripts/opportunity_synthesis.py`**

```python
#!/usr/bin/env python3
"""P4 nightly opportunity learning loop.
Finds high-scored-but-poorly-demoed opportunities (score-vs-demo divergence),
writes a learnings note, and tunes agents/opportunity_worker.md via Gemini.
Runs via the daily learning hook in run_cycle.
"""
import logging
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
LEDGER_FILE = ROOT / "vault" / "opportunities" / "ledger.md"
LEARNINGS_DIR = ROOT / "vault" / "learnings"
PROMPT_FILE = ROOT / "agents" / "opportunity_worker.md"


def _rows() -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    out = []
    for line in LEDGER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("| slug") or set(line) <= set("|- "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 9:
            out.append({"slug": cells[0], "composite": cells[1], "poc": cells[3]})
    return out


def find_divergence(threshold: float = 75) -> list[dict]:
    diverging = []
    for r in _rows():
        try:
            score = float(r["composite"])
        except ValueError:
            continue
        if score >= threshold and r["poc"] in ("weak", "dead"):
            diverging.append(r)
    return diverging


def write_learnings(diverging: list[dict]) -> Path:
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out = LEARNINGS_DIR / f"{today}-opportunities.md"
    lines = [f"# Opportunity Learnings — {today}", ""]
    if diverging:
        lines.append("## Score-vs-demo divergence (scored high, demoed poorly)")
        for r in diverging:
            lines.append(f"- [[{r['slug']}]] — composite {r['composite']} but PoC {r['poc']}")
        lines.append("")
        lines.append("These patterns are over-scored. The scout should weight them down next run.")
    else:
        lines.append("_No divergence today — scoring and demos aligned._")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _tune_prompt(diverging: list[dict]) -> None:
    if not diverging or not os.environ.get("GOOGLE_AI_API_KEY"):
        return
    current = PROMPT_FILE.read_text(encoding="utf-8")
    divergence_text = "\n".join(f"- {r['slug']}: scored {r['composite']}, demoed {r['poc']}" for r in diverging)
    client = OpenAI(
        api_key=os.environ["GOOGLE_AI_API_KEY"],
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    try:
        resp = client.chat.completions.create(
            model="gemini-2.5-flash",
            max_tokens=4096,
            messages=[
                {"role": "system", "content": (
                    "You tune the Prospector scout's prompt. Given ideas that scored high but demoed poorly, "
                    "add or refine 1-3 concrete scoring cautions so the scout stops over-scoring similar ideas. "
                    "Output the FULL revised markdown file, preserving all existing sections. Do not remove workflows."
                )},
                {"role": "user", "content": f"Diverging ideas:\n{divergence_text}\n\nCurrent prompt:\n{current}"},
            ],
        )
        new = resp.choices[0].message.content or ""
        if new.strip() and "Scout workflow" in new:
            PROMPT_FILE.write_text(new, encoding="utf-8")
            log.info("Tuned opportunity_worker.md from %d diverging ideas", len(diverging))
    except Exception as exc:
        log.error("Prompt tune failed: %s", exc)


def run() -> None:
    diverging = find_divergence(75)
    write_learnings(diverging)
    _tune_prompt(diverging)
    log.info("Opportunity synthesis complete — %d diverging ideas", len(diverging))


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/runner/test_opportunity_synthesis.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/opportunity_synthesis.py tests/runner/test_opportunity_synthesis.py
git commit -m "feat(learning): P4 opportunity synthesis — divergence detection + prompt self-tuning"
```

---

### Task 15: Full-suite regression + isolation verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest -q`
Expected: all tests pass (existing + new). Fix any regression before continuing.

- [ ] **Step 2: Isolation check — Atlas unchanged**

Run: `python -c "import inspect, runner.main as m; print('opportunity' not in inspect.getsource(m._maybe_spawn_planning_task))"`
Expected: prints `True`.

- [ ] **Step 3: One full live cycle (real API cost — optional)**

Run: `python scripts/launch.py --once`
Verify: dashboard shows the board; `workspace/ledger/daily-spend.json` has `by_pod.opportunity_pod` within the $10 cap; any outreach/Tony tasks ran normally.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: full-suite regression + Prospector isolation verification"
```

---

## PHASE 5 — Graduation & Real P&L (separate plan, forward-looking)

Phase 5 is intentionally NOT broken into bite-sized tasks here. Per the spec it introduces an **approval-gated external payment-provider/affiliate integration** (Stripe/PayPal/affiliate APIs) — a distinct subsystem requiring real accounts/credentials. It gets its own spec → plan cycle when P1–P4 have proven out. This plan only ensures nothing blocks it:

- The ledger schema already carries `status` (supports `graduated`), a `pod` column, and an `est_rev_mo` estimate column kept separate from any future `actual_*` columns (Task 3) — real numbers never overwrite estimates.
- The dashboard board reads the ledger generically (Task 6) — a future P&L panel adds a new data source (`vault/revenue/ledger.md`) without changing the board.

**When starting Phase 5, write a new spec** (`docs/superpowers/specs/<date>-prospector-phase5-pnl.md`) covering: the revenue ledger schema, the approval-gated provider webhook/poll integration, the graduation command that converts an opportunity into a real pod entry, and the P&L panel. Then run writing-plans for it.

---

## Self-Review

**Spec coverage (spec § → task):**
- §3 roles/pod/task types/routing/model tiering → Task 4 ✓
- §3 C-seam (poc_grade swappable) → Task 4 (routing) + Task 13 (grade tool) ✓
- §4 vault layout (ledger, pages, _moc, poc dir) → Tasks 3, 6, 12 ✓
- §4 scoring schema + weights + composite → Task 3 ✓
- §4 auto-promotion 75/75 → Task 4 prompt + Tasks 11, 13 chain ✓
- §4 est/graduated/pod fields → Task 3 columns + Phase 5 note ✓
- §5 four-phase flow → Tasks 4, 11, 12, 13 ✓
- §6 Prospector memory (auto via role) → Task 4 (load_agent_memory automatic) ✓
- §6 P4 divergence learning → Task 14 ✓
- §6 shared hardening (loop agents, no-op/errored guard, Sage+Prospector, backlinks) → Tasks 9, 10 ✓
- §7 cross-platform daily hook + scout interval → Tasks 7, 8 ✓
- §8 dashboard board → Task 6 ✓
- §9 budget invariants (pod cap, per-PoC, cwd confine) → Tasks 1, 5, 12 ✓
- §10 Phase 5 → forward-looking section ✓

**Known limitation (documented, not a gap):** A hard mid-run $2/PoC cutoff is not enforced — the runner only checks budget between tasks. The per-PoC limit is operationally bounded by the $10 pod cap (Task 5) plus the prompt's "handful of calls" guidance; the `per_poc_limit_usd` config value (Task 1) is available for a future mid-run enforcement if PoC costs prove higher than expected. The optional Brave-primary provider reorder is intentionally excluded (Prospector reuses the existing chain where Brave is already tier 2).

**Placeholder scan:** No TBD/TODO in executable tasks. Phase 5 is deferred to its own spec by design, not a placeholder.

**Type/name consistency:** `composite_score`, `log_opportunity`, `grade_poc`, `poc_runner`, `scout_due`/`mark_scout_ran`, `daily_learning_due`/`mark_learning_ran`, `weekly_sage_due`/`mark_sage_ran`, `is_pod_budget_exceeded`/`get_pod_spend`/`get_pod_cap`, `TASK_MODEL_OVERRIDES`, `TOOL_SPEC_LOG`/`TOOL_SPEC_GRADE`, `POC_RUNNER_TOOL_SPEC`, `CODE_TOOL_SPEC` — used consistently across tasks.
