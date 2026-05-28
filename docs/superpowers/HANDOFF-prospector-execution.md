# Execution Handoff — Prospector Build (mid-flight)

**Resume point for the next session.** We are partway through executing
`docs/superpowers/plans/2026-05-27-prospector.md` (the 15-task TDD plan).
Tasks 1–3 are done and committed; Task 4 is the next to run.

## Read first (in order)
1. `CLAUDE.md` — engineering standards, safety rules, plan-first (plan already approved).
2. `docs/superpowers/HANDOFF-prospector.md` — original design/plan handoff + the **two cost levers**.
3. `docs/superpowers/plans/2026-05-27-prospector.md` — the work queue (Tasks 1–15).
4. This file — current progress + what was learned.

## How to execute (unchanged)
Use **superpowers:subagent-driven-development**: one fresh subagent per task, TDD,
commit per task. Work tasks in order. Controller verifies each commit (read the diff +
run pytest) rather than spinning up separate reviewer subagents for the mechanical tasks —
each task ships its own tests, which act as the spec-compliance gate.

## TWO COST LEVERS — do not conflate (operator's explicit instruction)
- **(A) Build cost:** dispatch implementer subagents on **Haiku** by default
  (`Agent` tool `model: "haiku"`). Use **Sonnet** only for judgment tasks:
  **4, 6, 11, 15** (and any task whose tests fail unexpectedly). Never use Opus to execute.
- **(B) Runtime/deployed model values:** the models the *live agents* use must stay
  **exactly as the plan picked them, by task fit — NOT cost-minimized.** Do not downgrade.
  Confirmed values for Task 4's `task_models:` block + MODELS entry:
  - `opportunity_scout` → `gemini-2.5-flash`
  - `opportunity_deepdive` → `gemini-2.5-pro`  (the one place depth pays off)
  - `opportunity_spec` → `gemini-2.5-flash`
  - `poc_grade` → `gemini-2.5-flash`
  - `poc_build` → routed to `heavy_worker` (Forge), stays its role default `moonshotai/kimi-k2.5`
  - `MODELS["opportunity_worker"]` → `gemini-2.5-flash`

## Progress so far
| Task | Status | Commit |
|------|--------|--------|
| 1 — per-pod budget tracking | done | `f7cd1db` |
| 2 — thread pod into record_spend | done | `53417b3` |
| (checkpoint of 7 shared WIP files) | done | `bccde6c` |
| 3 — log_opportunity tool | done | `26dd5ee` |
| 4 — register role/pod/task-types/model-tiering/tools | NEXT (use Sonnet) | — |
| 5–15 | pending | — |

All of Tasks 1–3 tests pass (`pytest -q` green for the new test files).

## CRITICAL context discovered this session
1. **The working tree had large pre-existing operator WIP** on the shared files this
   build modifies — it's the *foundational model-routing groundwork* the plan builds on
   (Vertex/Gemini routing + Gemini pricing in `base.py`, ~280 new lines in `main.py`, etc.).
   - This WIP is now committed, NOT lost: `base.py` + some `budgets.yaml` WIP got bundled
     into the Task 1/2 commits (commit messages understate their contents but content is
     intact), and the remaining 7 shared files were checkpointed in `bccde6c`.
   - **Lesson for remaining tasks:** never `git add -A`. Subagents must `git add` only the
     specific files the task touches. The shared files the plan modifies
     (`config/agents.yaml`, `runner/main.py`, `prompts.py`, `task_creator.py`,
     `dashboard/*`, `improvement_loop.py`) are now committed clean, so future task commits
     will be focused.
   - Operator's *unrelated* WIP (manager.md, market_research_worker.md, brand.yaml,
     web.py, files.py, vault_writer.py, tool_runner.py, cron_runner.py, reader.py,
     transitions.py, launch.py, requirements.txt, .gitignore, deleted POD-*.md tasks) was
     deliberately LEFT uncommitted — no task touches it, so it won't get swept in.
2. **`runner/tools/vault_memory.py` is NOT git-tracked** (`git ls-files` returns empty).
   Task 9 modifies `auto_write_task_memory` in it — the implementer must locate the file
   (it exists on disk / is imported by `main.py` line 34) and confirm before editing.
3. **Verified anchors in current `runner/main.py`** (post-checkpoint) for Task 4:
   - `MODELS: dict[str, str] = {` at line ~44; no `opportunity_worker` entry yet.
   - `ROLE_TOOLS: dict[str, list[dict]] = {` at line ~66.
   - `"heavy_worker": [FILE_TOOL_SPEC, MEMORY_TOOL_SPEC],` at line ~77 (exact, matches plan).
   - `model = MODELS.get(role_id, "gemini-2.5-flash-lite")` at line ~303 (exact, matches plan).
   - `run_task` at ~286, `run_cycle` at ~335; `_maybe_spawn_planning_task()` is called at
     ~344 and ~371 — add `_maybe_spawn_scout()` after the LAST call (~371) for Task 7.
   - Tool-spec import aliases already in use: `WEB_TOOL_SPEC`, `FILE_TOOL_SPEC`,
     `TASK_CREATOR_TOOL_SPEC`, `MEMORY_TOOL_SPEC` (from `vault_memory`), etc.
4. **`runner/tools/code.py` exists** with `TOOL_SPEC` (name `code_runner`) and `_is_forbidden`
   — so Task 4's `CODE_TOOL_SPEC` import and Task 12's `_is_forbidden` import are valid.
5. **Router** (`runner/tasks/router.py`) builds its table from each agent's
   `allowed_task_types` in `config/agents.yaml` (first-wins). Adding the `opportunity_worker`
   role with its task types + adding `poc_build` to `heavy_worker` is sufficient to make the
   Task 4 routing tests pass. `_routing_table` is module-global and cached — the test resets it.

## Isolation guarantee (Task 15 Step 2 verifies)
Never modify `_maybe_spawn_planning_task` (Atlas) or the outreach/Tony pipelines. Prospector
ships behind its own pod/role. Final check must print `True`:
`python -c "import inspect, runner.main as m; print('opportunity' not in inspect.getsource(m._maybe_spawn_planning_task))"`

## Done definition
All 15 tasks committed, `pytest -q` green, Opportunity Board renders at :8765, isolation
check prints `True`.

## Environment notes
- Windows / PowerShell. Bash tool works; tests run with `python -m pytest`.
- A GateGuard hook requires stating "facts" before the first Bash command / first file write of a session.
- There is a git safety hook (`.claude/hooks/safety-check.ps1`) — no `git add -A`,
  no destructive ops without explicit intent.
