# Prospector Graduation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a PoC grades "promising," auto-draft a sellable product landing page with a live Stripe Payment Link (deployed behind one human click), record real revenue via a `log_revenue` tool + ledger, rank opportunities by real revenue over composite, and bundle graduated products as upsells to warm outreach leads.

**Architecture:** A new revenue ledger module (`runner/ledger/revenue.py`) mirrors `budget.py` but is never merged with it on disk. A new pipeline step in `_advance_opportunity_pipeline()` fires on `poc == promising` and queues a builder `landing_build` task, writing a landing-state file so it never re-queues. The builder writes a draft page with a literal `__STRIPE_PAYMENT_LINK__` placeholder; a FastAPI deploy endpoint validates + injects the operator's live Stripe URL behind one human click. Revenue feeds a `rank_score` tuple that sorts real earners above projections.

**Tech Stack:** Python 3.x, FastAPI (dashboard), pytest (monkeypatch module-level paths + `tmp_path`), vanilla JS (dashboard), markdown ledgers in `vault/`, JSON mirrors in `workspace/ledger/`.

**Spec:** `docs/superpowers/specs/2026-05-28-prospector-graduation-layer-design.md`

**Conventions observed:**
- Ledger modules expose module-level path constants and read them at call time, so tests `monkeypatch.setattr(module, "LEDGER_DIR", tmp_path)` (see `tests/runner/test_budget.py`).
- Markdown ledgers are append-only; corrections are reversing rows.
- `create_task(task_type=...)` accepts a free-form string in Python calls; the `enum` only constrains the agent-facing TOOL_SPEC.
- FastAPI endpoints return plain dicts; POST bodies read via `await request.json()`.
- Run all tests with: `python -m pytest -q`

---

### Task 1: Revenue ledger module

**Files:**
- Create: `runner/ledger/revenue.py`
- Test: `tests/runner/test_revenue.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runner/test_revenue.py
import json
import pytest
from runner.ledger import revenue as rev


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")


def test_record_revenue_creates_file(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    data = json.loads((tmp_path / "revenue.json").read_text())
    assert data["total_usd"] == pytest.approx(49.00)
    assert data["by_pod"]["ai-x"] == pytest.approx(49.00)
    assert "ch_1" in data["seen_external_ids"]


def test_record_revenue_dedups_external_id(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    assert rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")["recorded"] is True
    second = rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    assert second["recorded"] is False
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.00)


def test_reversing_row_reduces_total(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 49.00, "stripe", "ch_1")
    rev.record_revenue("ai-x", -49.00, "stripe", "re_1", kind="refund")
    assert rev.get_pod_revenue("ai-x") == pytest.approx(0.0)
    assert rev.get_revenue_total() == pytest.approx(0.0)


def test_manual_entry_skips_dedup(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rev.record_revenue("ai-x", 10.0, "manual", "", kind="manual")
    rev.record_revenue("ai-x", 10.0, "manual", "", kind="manual")
    assert rev.get_pod_revenue("ai-x") == pytest.approx(20.0)


def test_does_not_reset_daily(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    (tmp_path / "revenue.json").write_text(json.dumps(
        {"by_pod": {"ai-x": 100.0}, "total_usd": 100.0, "seen_external_ids": []}))
    assert rev.get_pod_revenue("ai-x") == pytest.approx(100.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runner/test_revenue.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'runner.ledger.revenue'`

- [ ] **Step 3: Write the implementation**

```python
# runner/ledger/revenue.py
import json
from pathlib import Path

LEDGER_DIR = Path(__file__).parent.parent.parent / "workspace" / "ledger"
REVENUE_FILE = LEDGER_DIR / "revenue.json"


def _load() -> dict:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if not REVENUE_FILE.exists():
        return {"by_pod": {}, "total_usd": 0.0, "seen_external_ids": []}
    try:
        data = json.loads(REVENUE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_pod": {}, "total_usd": 0.0, "seen_external_ids": []}
    data.setdefault("by_pod", {})
    data.setdefault("total_usd", 0.0)
    data.setdefault("seen_external_ids", [])
    return data


def _save(data: dict) -> None:
    REVENUE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_revenue(pod: str, amount_usd: float, source: str, external_id: str,
                   kind: str = "sale") -> dict:
    """Append a revenue event to the machine mirror. Dedup is keyed on a
    non-empty external_id (Stripe charge id); manual/adjustment rows pass an
    empty external_id and are never deduped. Returns {recorded: bool}."""
    data = _load()
    if external_id and external_id in data["seen_external_ids"]:
        return {"recorded": False, "reason": "duplicate external_id", "external_id": external_id}
    data["total_usd"] = round(data["total_usd"] + amount_usd, 6)
    data["by_pod"][pod] = round(data["by_pod"].get(pod, 0.0) + amount_usd, 6)
    if external_id:
        data["seen_external_ids"].append(external_id)
    _save(data)
    return {"recorded": True, "pod": pod, "amount_usd": amount_usd, "kind": kind}


def get_pod_revenue(pod: str) -> float:
    return _load()["by_pod"].get(pod, 0.0)


def get_revenue_total() -> float:
    return _load()["total_usd"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/runner/test_revenue.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add runner/ledger/revenue.py tests/runner/test_revenue.py
git commit -m "feat(revenue): add append-only revenue ledger module (mirror of budget.py)"
```

---

### Task 2: `log_revenue` tool

**Files:**
- Create: `runner/tools/revenue_tool.py`
- Modify: `runner/agents/tool_runner.py` (register the tool for CLI/operator use, NOT in any agent's tool list)
- Test: `tests/runner/test_revenue_tool.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runner/test_revenue_tool.py
import pytest
from runner.tools import revenue_tool as rt
from runner.ledger import revenue as rev


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")
    monkeypatch.setattr(rt, "REVENUE_MD", tmp_path / "ledger.md")


def test_log_revenue_writes_md_and_mirror(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    out = rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1", note="Pro plan")
    assert out["success"] is True
    md = (tmp_path / "ledger.md").read_text()
    assert "| ai-x | 49.0 | sale | stripe | ch_1 | Pro plan |" in md
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.0)


def test_log_revenue_dedup_does_not_append_md(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1")
    rt.log_revenue("ai-x", 49.0, source="stripe", external_id="ch_1")
    md_rows = [l for l in (tmp_path / "ledger.md").read_text().splitlines()
               if "ch_1" in l]
    assert len(md_rows) == 1


def test_log_revenue_rejects_bad_amount(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    out = rt.log_revenue("ai-x", "not-a-number", source="manual", external_id="")
    assert "error" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runner/test_revenue_tool.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'runner.tools.revenue_tool'`

- [ ] **Step 3: Write the implementation**

```python
# runner/tools/revenue_tool.py
from datetime import datetime
from pathlib import Path

from runner.ledger.revenue import record_revenue

REVENUE_MD = Path(__file__).parent.parent.parent / "vault" / "revenue" / "ledger.md"

_HEADER = (
    "# Revenue Ledger\n\n"
    "| date | pod | amount_usd | kind | source | external_id | note |\n"
    "|------|-----|-----------|------|--------|-------------|------|\n"
)
_VALID_KINDS = {"sale", "refund", "adjustment", "manual"}


def log_revenue(pod: str, amount_usd, source: str, external_id: str = "",
                kind: str = "sale", note: str = "") -> dict:
    """Record a real revenue event (sale/refund/adjustment/manual). Append-only;
    a correction is a reversing row with a negative amount. Dedups Stripe rows by
    external_id. Operator/CLI/dashboard only — never called autonomously by an agent."""
    try:
        amount = float(amount_usd)
    except (TypeError, ValueError):
        return {"error": f"amount_usd must be a number, got {amount_usd!r}"}
    if kind not in _VALID_KINDS:
        return {"error": f"kind must be one of {sorted(_VALID_KINDS)}"}

    result = record_revenue(pod, amount, source, external_id, kind=kind)
    if not result["recorded"]:
        return {"skipped": True, "reason": result.get("reason"), "external_id": external_id}

    REVENUE_MD.parent.mkdir(parents=True, exist_ok=True)
    if not REVENUE_MD.exists():
        REVENUE_MD.write_text(_HEADER, encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")
    row = f"| {today} | {pod} | {amount} | {kind} | {source} | {external_id} | {note} |\n"
    with REVENUE_MD.open("a", encoding="utf-8") as fh:
        fh.write(row)
    return {"success": True, "pod": pod, "amount_usd": amount, "kind": kind}


TOOL_SPEC = {
    "name": "log_revenue",
    "description": (
        "Record a REAL revenue event to the revenue ledger (sale, refund, adjustment, or manual "
        "entry). Append-only — a correction is a reversing row with a negative amount_usd. Stripe "
        "rows dedup by external_id. Operator-invoked only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pod": {"type": "string", "description": "Pod/product id the revenue belongs to."},
            "amount_usd": {"type": "number", "description": "USD amount; negative for a refund/reversal."},
            "source": {"type": "string", "description": "e.g. 'stripe', 'manual', 'cash'."},
            "external_id": {"type": "string", "description": "Provider txn id for dedup; blank for manual."},
            "kind": {"type": "string", "enum": ["sale", "refund", "adjustment", "manual"]},
            "note": {"type": "string", "description": "Optional human note."},
        },
        "required": ["pod", "amount_usd", "source"],
    },
}
```

- [ ] **Step 4: Register the tool (CLI/operator only — do NOT add to any AGENT_TOOLS list)**

In `runner/agents/tool_runner.py`, after the existing `from runner.tools.opportunity import ...` block (around line 24), add:

```python
from runner.tools.revenue_tool import log_revenue
```

And after `register_tool("update_opportunity",  update_opportunity)` (around line 45) add:

```python
register_tool("log_revenue",         log_revenue)
```

Do NOT add `log_revenue` to the per-agent tool map in `runner/main.py` (lines 87-102): revenue is operator-only and must never be written autonomously by an agent (spec §5.4).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/runner/test_revenue_tool.py -q`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add runner/tools/revenue_tool.py runner/agents/tool_runner.py tests/runner/test_revenue_tool.py
git commit -m "feat(revenue): add log_revenue tool (operator-only, append-only md + mirror)"
```

---

### Task 3: Revenue-ranked sort key

**Files:**
- Modify: `runner/tools/opportunity.py` (add `rank_score` after `read_ledger`, ~line 72)
- Test: `tests/runner/test_rank_score.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/runner/test_rank_score.py
import pytest
from runner.tools import opportunity as opp


def _row(slug, composite, pod="—"):
    return {"slug": slug, "composite": composite, "phase": "graded",
            "poc": "promising", "system_fit": "7", "est_rev_mo": "500",
            "status": "graded", "pod": pod, "updated": "2026-05-28"}


def test_earner_outranks_higher_composite(monkeypatch):
    monkeypatch.setattr(opp, "get_pod_revenue",
                        lambda pod: 312.0 if pod == "ai-earner" else 0.0)
    earner = _row("ai-earner", 40.0, pod="ai-earner")
    projection = _row("ai-hype", 95.0, pod="—")
    ranked = sorted([projection, earner], key=opp.rank_score, reverse=True)
    assert ranked[0]["slug"] == "ai-earner"


def test_earners_order_by_revenue(monkeypatch):
    rev = {"a": 100.0, "b": 500.0}
    monkeypatch.setattr(opp, "get_pod_revenue", lambda pod: rev.get(pod, 0.0))
    ranked = sorted([_row("a", 90.0, "a"), _row("b", 10.0, "b")],
                    key=opp.rank_score, reverse=True)
    assert [r["slug"] for r in ranked] == ["b", "a"]


def test_non_earners_order_by_composite(monkeypatch):
    monkeypatch.setattr(opp, "get_pod_revenue", lambda pod: 0.0)
    ranked = sorted([_row("low", 30.0), _row("high", 80.0)],
                    key=opp.rank_score, reverse=True)
    assert [r["slug"] for r in ranked] == ["high", "low"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runner/test_rank_score.py -q`
Expected: FAIL — `AttributeError: module 'runner.tools.opportunity' has no attribute 'rank_score'`

- [ ] **Step 3: Write the implementation**

At the top of `runner/tools/opportunity.py`, after the existing imports (line 3), add:

```python
from runner.ledger.revenue import get_pod_revenue
```

Then add this function immediately after `read_ledger()` (after line 71):

```python
def rank_score(row: dict) -> tuple:
    """Sort key: real revenue dominates the internal composite. Returns
    (has_revenue, revenue_usd, composite) so any earning opportunity outranks
    any projection-only one; earners order by revenue, the rest by composite.
    Use with sorted(..., key=rank_score, reverse=True)."""
    pod = row.get("pod", "—")
    revenue = get_pod_revenue(pod) if pod not in ("—", "-", "", None) else 0.0
    try:
        composite = float(row.get("composite", 0.0))
    except (TypeError, ValueError):
        composite = 0.0
    return (1 if revenue > 0 else 0, revenue, composite)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/runner/test_rank_score.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add runner/tools/opportunity.py tests/runner/test_rank_score.py
git commit -m "feat(prospector): rank_score makes real revenue outrank composite"
```

---

### Task 4: Landing-state helpers + graduation pipeline step

**Files:**
- Create: `runner/tools/landing.py` (landing-state read/write helpers)
- Modify: `runner/main.py` `_advance_opportunity_pipeline()` (add graduation step; switch selections to `rank_score`)
- Test: `tests/runner/test_landing_state.py`, `tests/runner/test_graduation_step.py`

- [ ] **Step 1: Write the failing landing-state tests**

```python
# tests/runner/test_landing_state.py
from runner.tools import landing


def _patch(monkeypatch, tmp_path):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)


def test_landing_absent_then_present(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    assert landing.landing_exists("ai-x") is False
    landing.write_landing_state("ai-x", status="draft")
    assert landing.landing_exists("ai-x") is True
    assert landing.read_landing_state("ai-x")["status"] == "draft"


def test_deploy_fields_persist(tmp_path, monkeypatch):
    _patch(monkeypatch, tmp_path)
    landing.write_landing_state("ai-x", status="draft")
    landing.write_landing_state("ai-x", status="deployed",
                                payment_link_url="https://buy.stripe.com/abc",
                                public_url="https://easysimplesites.org/ai-x")
    s = landing.read_landing_state("ai-x")
    assert s["status"] == "deployed"
    assert s["payment_link_url"].startswith("https://buy.stripe.com/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/runner/test_landing_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'runner.tools.landing'`

- [ ] **Step 3: Write the landing-state helper**

```python
# runner/tools/landing.py
import json
from datetime import datetime
from pathlib import Path

LANDINGS_DIR = Path(__file__).parent.parent.parent / "workspace" / "landings"


def _path(slug: str) -> Path:
    return LANDINGS_DIR / f"{slug}.json"


def landing_exists(slug: str) -> bool:
    return _path(slug).exists()


def read_landing_state(slug: str) -> dict:
    p = _path(slug)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_landing_state(slug: str, status: str, **extra) -> dict:
    """Upsert the landing-state file. Merges extra fields (payment_link_url,
    public_url, deployed_at) over any existing state."""
    LANDINGS_DIR.mkdir(parents=True, exist_ok=True)
    state = read_landing_state(slug)
    state["slug"] = slug
    state["status"] = status
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state.update(extra)
    _path(slug).write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state
```

- [ ] **Step 4: Run landing-state tests to verify they pass**

Run: `python -m pytest tests/runner/test_landing_state.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Write the failing graduation-step test**

```python
# tests/runner/test_graduation_step.py
import runner.main as main
from runner.tools import landing


def test_promising_row_queues_landing_build(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    # No opportunity work already queued
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    rows = [
        {"slug": "ai-x", "composite": 80.0, "phase": "graded", "poc": "promising",
         "system_fit": "7", "est_rev_mo": "500", "status": "graded",
         "pod": "—", "updated": "2026-05-28"},
    ]
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: rows)

    created = {}
    def fake_create_task(**kw):
        created.update(kw)
        return {"success": True, "task_id": "T1"}
    monkeypatch.setattr(main, "create_task", fake_create_task)

    main._advance_opportunity_pipeline()

    assert created.get("assigned_agent") == "builder"
    assert created.get("task_type") == "landing_build"
    assert "ai-x" in created.get("title", "")
    assert landing.landing_exists("ai-x") is True


def test_promising_row_with_landing_not_requeued(tmp_path, monkeypatch):
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path)
    landing.write_landing_state("ai-x", status="draft")
    monkeypatch.setattr(main, "is_pod_budget_exceeded", lambda pod: False)
    monkeypatch.setattr(main, "_opportunity_task_pending", lambda: False)
    rows = [
        {"slug": "ai-x", "composite": 80.0, "phase": "graded", "poc": "promising",
         "system_fit": "7", "est_rev_mo": "500", "status": "graded",
         "pod": "—", "updated": "2026-05-28"},
    ]
    monkeypatch.setattr("runner.tools.opportunity.read_ledger", lambda: rows)
    calls = []
    monkeypatch.setattr(main, "create_task", lambda **kw: calls.append(kw) or {"success": True})

    main._advance_opportunity_pipeline()

    # ai-x already has a landing; with no scouted/deepdived work it falls through
    # to the scout fallback, never a landing_build for ai-x.
    assert not any(c.get("task_type") == "landing_build" for c in calls)
```

> **Note for implementer:** The test references `main._opportunity_task_pending`. Read the current top of `_advance_opportunity_pipeline()` (runner/main.py:318-338) to find the actual guard it uses for "is opportunity work already queued" and name the monkeypatch to match. If the guard is inline rather than a named function, extract it into a module-level `_opportunity_task_pending()` helper as Step 6a (a pure refactor, no behavior change) so it is patchable, then run the existing pipeline tests to confirm no regression before continuing.

- [ ] **Step 6: Run graduation-step test to verify it fails**

Run: `python -m pytest tests/runner/test_graduation_step.py -q`
Expected: FAIL — the pipeline has no landing_build step yet, so `created` stays empty.

- [ ] **Step 7: Implement the graduation step**

In `runner/main.py`, add the import near the other opportunity imports (line 37 region):

```python
from runner.tools.landing import landing_exists, write_landing_state
from runner.tools.opportunity import rank_score
```

In `_advance_opportunity_pipeline()`:

(a) Change the scouted selection (line 343) from:

```python
        top = max(scouted, key=lambda r: r["composite"])
```
to:
```python
        top = max(scouted, key=rank_score)
```

(b) Change the buildable selection (line 359) from:

```python
        top = max(buildable, key=lambda r: r["composite"])
```
to:
```python
        top = max(buildable, key=rank_score)
```

(c) Insert this new block AFTER the PoC-build step (after its `return`, ~line 368) and BEFORE the "scout a fresh batch" fallback (line 370):

```python
    # 2.5) Graduate a promising PoC into a draft landing page (autonomous build;
    # deploy stays behind the dashboard's one-click human gate).
    promising = [r for r in rows
                 if r.get("poc") == "promising" and not landing_exists(r["slug"])]
    if promising:
        top = max(promising, key=rank_score)
        write_landing_state(top["slug"], status="queued")
        create_task(
            title=f"Landing build: {top['slug']}",
            body=(f"Build a one-page product landing page for the graduated opportunity "
                  f"[[{top['slug']}]]. Read its value prop, who-pays, and pricing from "
                  f"vault/opportunities/{top['slug']}.md. Follow the 'Product Landing Page "
                  f"(landing_build)' section of your system prompt. Save the page to "
                  f"workspace/sites/{top['slug']}/index.html with the CTA button's href set to "
                  f"the literal placeholder __STRIPE_PAYMENT_LINK__ (do NOT invent a URL — the "
                  f"operator injects the live Stripe Payment Link at deploy). End your summary "
                  f"with: LANDING DRAFTED: {top['slug']}"),
            assigned_agent="builder", task_type="landing_build",
            pod="opportunity_pod", priority="normal")
        log.info("Pipeline: landing build %s", top["slug"])
        return
```

> If `is_pod_budget_exceeded` / `create_task` / `read_ledger` are imported names inside the function rather than module-level, keep them where they are — the tests patch them on `main`, so ensure they are referenced as module-level names (they already are per runner/main.py:324-326).

- [ ] **Step 8: Run the graduation-step tests to verify they pass**

Run: `python -m pytest tests/runner/test_graduation_step.py tests/runner/test_landing_state.py -q`
Expected: PASS (4 passed)

- [ ] **Step 9: Run the existing pipeline/runner tests to confirm no regression**

Run: `python -m pytest tests/runner -q`
Expected: PASS (all green)

- [ ] **Step 10: Commit**

```bash
git add runner/tools/landing.py runner/main.py tests/runner/test_landing_state.py tests/runner/test_graduation_step.py
git commit -m "feat(prospector): graduation step queues builder landing_build on promising grade"
```

---

### Task 5: Builder landing-page behavior (prompt)

**Files:**
- Modify: `agents/builder.md` (add a new task-type section)

- [ ] **Step 1: Add the landing_build section**

Append this section to `agents/builder.md` after the "## Quality rules" section:

```markdown
## Product Landing Page (landing_build)

When a task has `task_type: landing_build`, you are NOT building a client site — you are building a one-page sales landing for one of OUR OWN graduated AI products under easysimplesites.org.

### Source
Read `vault/opportunities/<slug>.md` for the product's value prop, who-pays, and pricing hypothesis (the slug is in the task title/body).

### Output — `workspace/sites/<slug>/index.html`, one page:
1. **Hero** — the product name + the one-liner value prop, a single clear sentence on what it does.
2. **Proof** — 2-3 bullet points of the concrete value the PoC demonstrated (pull from the opportunity page).
3. **Pricing** — the price/tier from the pricing hypothesis. If multiple tiers, show them; if unclear, show one price and note it in your summary so the operator can adjust before deploy.
4. **CTA button** — a prominent button whose `href` is the LITERAL string `__STRIPE_PAYMENT_LINK__`. Do NOT invent, guess, or paste any real URL. The operator injects the live Stripe Payment Link at deploy time.
5. **Footer** — `© [Year] Easy Simple Sites · easysimplesites.org`.

### Rules
- Same design standards as client sites: mobile-first, embedded CSS, Google Fonts CDN only, no JS frameworks.
- The CTA `href` MUST remain `__STRIPE_PAYMENT_LINK__` exactly — the deploy step validates and replaces it. A page that ships a real or fake URL here is a defect.
- Do NOT deploy. Do NOT write to `workspace/landings/`. The runner and the deploy gate own that state.
- End your response with: `LANDING DRAFTED: <slug>`

### Log to memory
Call `write_memory` (role_id: builder, entry_type: success) with the product slug and the design choices you made.
```

- [ ] **Step 2: Commit**

```bash
git add agents/builder.md
git commit -m "feat(builder): add landing_build product landing page behavior"
```

---

### Task 6: Deploy endpoints + upsell-catalog append

**Files:**
- Modify: `dashboard/server.py` (add `/api/landing/pending`, `/api/landing/deploy`; import landing helpers)
- Test: `tests/dashboard/test_landing_deploy.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/dashboard/test_landing_deploy.py
import json
import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.tools import landing


@pytest.fixture
def client(tmp_path, monkeypatch):
    sites = tmp_path / "sites"
    (sites / "ai-x").mkdir(parents=True)
    (sites / "ai-x" / "index.html").write_text(
        '<a href="__STRIPE_PAYMENT_LINK__" class="cta">Buy</a>', encoding="utf-8")
    monkeypatch.setattr(landing, "LANDINGS_DIR", tmp_path / "landings")
    landing.write_landing_state("ai-x", status="draft")
    monkeypatch.setattr(server, "SITES_DIR", sites)
    monkeypatch.setattr(server, "UPSELL_CATALOG", tmp_path / "upsell-catalog.md")
    return TestClient(server.app)


def test_pending_lists_draft(client):
    r = client.get("/api/landing/pending")
    assert r.status_code == 200
    assert any(d["slug"] == "ai-x" for d in r.json()["pending"])


def test_deploy_injects_valid_stripe_url(client, tmp_path):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "https://buy.stripe.com/test_abc"})
    assert r.json()["success"] is True
    html = (tmp_path / "sites" / "ai-x" / "index.html").read_text()
    assert "https://buy.stripe.com/test_abc" in html
    assert "__STRIPE_PAYMENT_LINK__" not in html
    assert landing.read_landing_state("ai-x")["status"] == "deployed"
    catalog = (tmp_path / "upsell-catalog.md").read_text()
    assert "ai-x" in catalog


def test_deploy_rejects_non_stripe_url(client, tmp_path):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "https://evil.example.com/pay"})
    assert "error" in r.json()
    html = (tmp_path / "sites" / "ai-x" / "index.html").read_text()
    assert "__STRIPE_PAYMENT_LINK__" in html  # unchanged
    assert landing.read_landing_state("ai-x")["status"] == "draft"


def test_deploy_rejects_placeholder_passthrough(client):
    r = client.post("/api/landing/deploy",
                    json={"slug": "ai-x", "payment_link_url": "__STRIPE_PAYMENT_LINK__"})
    assert "error" in r.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/dashboard/test_landing_deploy.py -q`
Expected: FAIL — endpoints/attrs not defined (404 / AttributeError).

- [ ] **Step 3: Implement the endpoints**

In `dashboard/server.py`, add near the other module constants (after `STATE_FILE`, line 11):

```python
SITES_DIR = Path(__file__).parent.parent / "workspace" / "sites"
UPSELL_CATALOG = Path(__file__).parent.parent / "vault" / "revenue" / "upsell-catalog.md"
_STRIPE_URL_RE = re.compile(r"^https://(?:buy\.stripe\.com|[a-z0-9.-]+\.stripe\.com)/\S+$")
_UPSELL_HEADER = (
    "# Upsell Catalog\n\n"
    "| product | one_liner | landing_url | fits_business_types |\n"
    "|---------|-----------|-------------|---------------------|\n"
)
```

> `re` and `Path` are already imported at the top of server.py (lines 1-5).

Add these endpoints (place them after the `/api/outreach/followup-sweep` block, ~line 292):

```python
@app.get("/api/landing/pending")
async def api_landing_pending():
    """Draft product landing pages awaiting the operator's one-click deploy."""
    from runner.tools.landing import LANDINGS_DIR, read_landing_state
    pending = []
    if LANDINGS_DIR.exists():
        for f in LANDINGS_DIR.glob("*.json"):
            state = read_landing_state(f.stem)
            if state.get("status") in ("queued", "draft"):
                pending.append({"slug": f.stem, "status": state.get("status")})
    return {"pending": pending}


@app.post("/api/landing/deploy")
async def api_landing_deploy(request: Request):
    """Inject the operator's LIVE Stripe Payment Link into a draft landing page
    and mark it deployed. This is the single human money-gate: the live link
    enters the system only here, only on an explicit click, and only if it
    validates as a Stripe URL."""
    from runner.tools.landing import read_landing_state, write_landing_state

    data = await request.json()
    slug = (data.get("slug") or "").strip()
    url = (data.get("payment_link_url") or "").strip()
    if not slug:
        return {"error": "slug required"}
    if not _STRIPE_URL_RE.match(url):
        return {"error": "payment_link_url must be a valid Stripe link (https://buy.stripe.com/...)"}

    state = read_landing_state(slug)
    if not state:
        return {"error": f"no landing draft found for {slug!r}"}

    index = SITES_DIR / slug / "index.html"
    if not index.exists():
        return {"error": f"landing page not built yet for {slug!r} (no index.html)"}
    html = index.read_text(encoding="utf-8")
    if "__STRIPE_PAYMENT_LINK__" not in html:
        return {"error": "placeholder __STRIPE_PAYMENT_LINK__ not found in page"}
    index.write_text(html.replace("__STRIPE_PAYMENT_LINK__", url), encoding="utf-8")

    public_url = f"https://easysimplesites.org/{slug}"
    write_landing_state(slug, status="deployed", payment_link_url=url, public_url=public_url)

    UPSELL_CATALOG.parent.mkdir(parents=True, exist_ok=True)
    if not UPSELL_CATALOG.exists():
        UPSELL_CATALOG.write_text(_UPSELL_HEADER, encoding="utf-8")
    one_liner = state.get("one_liner", slug)
    with UPSELL_CATALOG.open("a", encoding="utf-8") as fh:
        fh.write(f"| {slug} | {one_liner} | {public_url} |  |\n")

    return {"success": True, "slug": slug, "public_url": public_url,
            "next_step": f"Drag workspace/sites/{slug}/ to app.netlify.com/drop to publish."}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/dashboard/test_landing_deploy.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add dashboard/server.py tests/dashboard/test_landing_deploy.py
git commit -m "feat(dashboard): landing deploy gate validates+injects live Stripe link, appends upsell catalog"
```

---

### Task 7: log-revenue + P&L endpoints

**Files:**
- Modify: `dashboard/server.py` (add `/api/revenue/log`, `/api/pnl`)
- Test: `tests/dashboard/test_revenue_endpoints.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/dashboard/test_revenue_endpoints.py
import pytest
from fastapi.testclient import TestClient
import dashboard.server as server
from runner.ledger import revenue as rev
from runner.tools import revenue_tool as rt


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(rev, "LEDGER_DIR", tmp_path)
    monkeypatch.setattr(rev, "REVENUE_FILE", tmp_path / "revenue.json")
    monkeypatch.setattr(rt, "REVENUE_MD", tmp_path / "ledger.md")
    return TestClient(server.app)


def test_log_revenue_endpoint(client, tmp_path):
    r = client.post("/api/revenue/log",
                    json={"pod": "ai-x", "amount_usd": 49.0, "source": "manual", "kind": "manual"})
    assert r.json()["success"] is True
    assert rev.get_pod_revenue("ai-x") == pytest.approx(49.0)


def test_log_revenue_endpoint_bad_amount(client):
    r = client.post("/api/revenue/log",
                    json={"pod": "ai-x", "amount_usd": "abc", "source": "manual"})
    assert "error" in r.json()


def test_pnl_returns_pod_rows(client, monkeypatch):
    monkeypatch.setattr(server, "read_opportunities",
                        lambda: [{"slug": "ai-x", "pod": "ai-x", "est_rev_mo": "500",
                                  "composite": "80", "phase": "graduated", "poc": "promising",
                                  "system_fit": "7", "status": "graduated", "updated": "2026-05-28"}])
    client.post("/api/revenue/log",
                json={"pod": "ai-x", "amount_usd": 120.0, "source": "manual", "kind": "manual"})
    r = client.get("/api/pnl")
    rows = r.json()["pods"]
    row = next(p for p in rows if p["pod"] == "ai-x")
    assert row["revenue_to_date"] == pytest.approx(120.0)
    assert row["est_rev_mo"] == pytest.approx(500.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/dashboard/test_revenue_endpoints.py -q`
Expected: FAIL — endpoints not defined (404).

- [ ] **Step 3: Implement the endpoints**

Add to `dashboard/server.py` after the `/api/landing/deploy` block:

```python
@app.post("/api/revenue/log")
async def api_revenue_log(request: Request):
    """Operator-only manual revenue entry, backing the dashboard 'Log Revenue' button."""
    from runner.tools.revenue_tool import log_revenue
    data = await request.json()
    return log_revenue(
        pod=(data.get("pod") or "").strip(),
        amount_usd=data.get("amount_usd"),
        source=(data.get("source") or "manual").strip(),
        external_id=(data.get("external_id") or "").strip(),
        kind=(data.get("kind") or "manual").strip(),
        note=(data.get("note") or "").strip(),
    )


@app.get("/api/pnl")
async def api_pnl():
    """Per-pod real revenue vs. the original est_rev_mo projection, net of spend."""
    from runner.ledger.revenue import get_pod_revenue
    from runner.ledger.budget import get_pod_spend
    pods = []
    for row in read_opportunities():
        pod = row.get("pod", "—")
        if pod in ("—", "-", "", None):
            continue
        try:
            est = float(row.get("est_rev_mo", 0) or 0)
        except (TypeError, ValueError):
            est = 0.0
        revenue = round(get_pod_revenue(pod), 2)
        spend = round(get_pod_spend(pod), 2)
        pods.append({
            "pod": pod, "slug": row.get("slug"),
            "est_rev_mo": est, "revenue_to_date": revenue,
            "spend_to_date": spend, "net": round(revenue - spend, 2),
        })
    return {"pods": pods}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/dashboard/test_revenue_endpoints.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add dashboard/server.py tests/dashboard/test_revenue_endpoints.py
git commit -m "feat(dashboard): /api/revenue/log and /api/pnl endpoints"
```

---

### Task 8: Dashboard UI — wire button, deploy card, P&L strip

**Files:**
- Modify: `dashboard/index.html` (lines 749-756 region + JS helpers near line 1199)

> **No automated test** — this is browser UI. Manual verification steps are in Step 3. State this explicitly when reporting completion.

- [ ] **Step 1: Replace the disabled button + add a deploy/P&L container**

In `dashboard/index.html`, replace the disabled button block (lines 754-755):

```html
        <button class="trigger-btn" disabled
                title="P5 — revenue ledger not built yet. See docs/superpowers/specs/2026-05-28-prospector-phase5-pnl.md (log_revenue tool).">💰 Log Revenue</button>
```

with:

```html
        <button class="trigger-btn" onclick="logRevenue(this)">💰 Log Revenue</button>
      </div>
      <div class="section-title" style="margin-bottom:6px">Graduated Products</div>
      <div id="landing-pending" style="font-size:10px;color:var(--muted)">Loading…</div>
      <div class="section-title" style="margin-bottom:6px">P&amp;L — Real vs. Projected</div>
      <div id="pnl-strip" style="font-size:10px;color:var(--muted)">Loading…</div>
```

> Note: the original `<div id="crm-actions">` already opens at line 750; the line above closes it after the new button. Verify the resulting HTML has exactly one matching `</div>` for `crm-actions` — the original close at line 756 is replaced by the one you added here (delete the now-duplicate old `</div>` at the old line 756 if it would double-close).

- [ ] **Step 2: Add the JS helpers**

Add near the other `async function` helpers (after `refreshCRM`, ~line 1230):

```javascript
async function logRevenue(btn) {
  const pod = prompt("Pod / product id (e.g. local_outreach_pod):");
  if (!pod) return;
  const amount = parseFloat(prompt("Amount USD (negative for a refund):"));
  if (isNaN(amount)) { alert("Amount must be a number"); return; }
  const note = prompt("Note (optional):") || "";
  const r = await fetch("/api/revenue/log", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pod, amount_usd: amount, source: "manual", kind: "manual", note }),
  }).then(r => r.json());
  alert(r.success ? `Logged $${amount} to ${pod}` : `Error: ${r.error || r.reason}`);
  refreshPnl();
}

async function deployLanding(slug) {
  const url = prompt(`Paste the LIVE Stripe Payment Link for "${slug}":`);
  if (!url) return;
  const r = await fetch("/api/landing/deploy", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, payment_link_url: url }),
  }).then(r => r.json());
  alert(r.success ? `Deployed. ${r.next_step}` : `Error: ${r.error}`);
  refreshLandings();
}

async function refreshLandings() {
  try {
    const d = await fetch("/api/landing/pending").then(r => r.json());
    const el = document.getElementById("landing-pending");
    if (!d.pending || d.pending.length === 0) { el.textContent = "No products awaiting deploy."; return; }
    el.innerHTML = d.pending.map(p =>
      `<div class="queue-row"><span>${p.slug} (${p.status})</span>` +
      `<button class="trigger-btn" onclick="deployLanding('${p.slug}')">🚀 Deploy</button></div>`).join("");
  } catch (e) { /* leave last-known */ }
}

async function refreshPnl() {
  try {
    const d = await fetch("/api/pnl").then(r => r.json());
    const el = document.getElementById("pnl-strip");
    if (!d.pods || d.pods.length === 0) { el.textContent = "No graduated pods yet."; return; }
    el.innerHTML = d.pods.map(p => {
      const cls = p.net < 0 ? "failed" : "done";
      return `<div class="queue-row"><span>${p.pod}</span>` +
             `<span class="queue-count ${cls}">$${p.revenue_to_date} real / $${p.est_rev_mo} est · net $${p.net}</span></div>`;
    }).join("");
  } catch (e) { /* leave last-known */ }
}
```

- [ ] **Step 3: Hook the refreshers into the CRM tab refresh + manual verify**

Find where `refreshCRM()` is called on the polling timer (search `refreshCRM(` in the polling/interval block) and add `refreshLandings(); refreshPnl();` alongside it.

Manual verification (the dashboard runs via `python scripts/start_dashboard.py`):
1. Start the dashboard, open the Outreach CRM tab.
2. Click **💰 Log Revenue**, enter a pod + amount → confirm the P&L strip updates and `vault/revenue/ledger.md` gains a row.
3. With a draft landing present (`workspace/landings/<slug>.json` status draft + a built `index.html`), confirm it appears under "Graduated Products" with a **Deploy** button.
4. Click **Deploy**, paste a `https://buy.stripe.com/test_...` URL → confirm success alert, the `index.html` placeholder is replaced, and the product appears in `vault/revenue/upsell-catalog.md`.
5. Paste a non-Stripe URL → confirm it is rejected and the page is unchanged.

- [ ] **Step 4: Commit**

```bash
git add dashboard/index.html
git commit -m "feat(dashboard): wire Log Revenue button, deploy cards, and P&L strip"
```

---

### Task 9: Outreach upsell behavior (prompt)

**Files:**
- Modify: `agents/outreach_worker.md` (add an upsell section)
- Note: `vault/revenue/upsell-catalog.md` is created on first deploy (Task 6) — no seed file needed.

- [ ] **Step 1: Add the upsell section to outreach_worker.md**

Append after the "## Non-Negotiable Rules" section in `agents/outreach_worker.md`:

```markdown
## Upsell to Warm Leads

At the start of each run, read `vault/revenue/upsell-catalog.md` (it may not exist yet — if absent, skip upselling entirely).

The catalog lists graduated AI products we sell, one row each:
`| product | one_liner | landing_url | fits_business_types |`

When you process a **warm lead** — a CRM row whose status is `replied` — AND a catalog product's `fits_business_types` plausibly matches that lead's business type (lenient match, same spirit as the IG-handle rule; if `fits_business_types` is blank, treat it as fitting any business), include ONE short upsell line in your follow-up, naming the product and its `landing_url`.

**Rules:**
- Only `replied` leads. NEVER upsell to `new`, `email_sent`, `dm_queued`, `call_queued`, `closed`, or `no_interest` leads.
- One upsell product per follow-up — pick the best-fitting one.
- The site offer ($299/$499/$799) stays the primary pitch; the upsell is a single added line, not a replacement.
- If the catalog is empty or no product fits, send the normal follow-up with no upsell.
```

- [ ] **Step 2: Commit**

```bash
git add agents/outreach_worker.md
git commit -m "feat(outreach): offer graduated products as upsells to replied warm leads"
```

---

### Task 10: Full suite + isolation verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS (all green, including the pre-existing budget/dashboard tests).

- [ ] **Step 2: Verify spend ledger is untouched (isolation)**

Run: `git log --oneline -- runner/ledger/budget.py | head -1` then `git diff HEAD~9 -- runner/ledger/budget.py`
Expected: NO diff output — `budget.py` was never modified by this work.

- [ ] **Step 3: Verify log_revenue is NOT in any agent tool list**

Run: `python -c "import runner.main as m; print([t['name'] for lst in m.AGENT_TOOLS.values() for t in lst if t['name']=='log_revenue'])"`
Expected: `[]` (empty — revenue is operator-only).

> If the per-agent tool dict in runner/main.py (lines 87-102) is named something other than `AGENT_TOOLS`, grep for it and adjust the attribute name in the command above.

- [ ] **Step 4: Verify no Stripe credentials in files**

Run (PowerShell): `Select-String -Path (Get-ChildItem -Recurse -File -Exclude *.md) -Pattern "sk_live|sk_test|rk_live" | Select-Object -First 5`
Expected: NO matches — no Stripe secret key anywhere in the tree (the live Payment Link URL is operator-pasted at runtime, never stored in a source file).

- [ ] **Step 5: Final commit (only if a verification fix was needed)**

```bash
git add -A
git commit -m "test: full-suite + isolation verification for graduation layer"
```

---

## Self-Review

**Spec coverage:**
- §5.1 graduation step → Task 4. §5.2 builder landing → Task 5. §5.3 deploy gate → Task 6. §5.4 log_revenue + ledger → Tasks 1-2. §5.5 dashboard button + P&L strip → Tasks 7-8. §5.6 rank_score → Task 3. §5.7 upsell catalog + outreach → Tasks 6 (append) + 9 (behavior). Success criteria 1-8 (§8) map to Tasks 4, 6, 1-2, 7-8, 3, 9, 10, 10. No gaps.

**Decisions honored:** auto-build draft + human deploy (Task 4 queues, Task 6 gates); live Payment Link injected only at deploy (Task 6); feedback loop in v1 (Task 3); upsell `replied` + type-fit (Task 9).

**Placeholder scan:** every code step contains complete code; doc-edit steps contain the full prose to insert. The two "if named differently, adjust" notes (Task 4 guard helper, Task 10 AGENT_TOOLS attribute) are deliberate guardrails against drift in files whose internal naming the implementer must confirm against the live source, not missing content.

**Type consistency:** `record_revenue(pod, amount_usd, source, external_id, kind)` consistent across Tasks 1-2-7. `rank_score(row) -> tuple` consistent Tasks 3-4. `write_landing_state(slug, status, **extra)` / `read_landing_state` / `landing_exists` consistent Tasks 4-6. Endpoint shapes (`/api/landing/pending` → `{pending:[...]}`, `/api/pnl` → `{pods:[...]}`, `/api/landing/deploy` → `{success, public_url, next_step}` or `{error}`) match between server impl and JS/test consumers.
