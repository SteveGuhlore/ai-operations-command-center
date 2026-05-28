# Runbook — Deploy `feat/prospector-phases-1-4`

**Date:** 2026-05-28
**Branch:** `feat/prospector-phases-1-4` (14 commits off `master`)
**Worktree:** `C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules`
**Main repo (running app):** `C:/Users/alexa/Downloads/AI Operations Command Center`

Copy-paste, top to bottom. Two working directories are used — each block says which.
Stay calm at §3: ~20 test failures are **expected, pre-existing noise**. The real
signal is the 116 new tests in §3b.

> **Heads-up (correction to the handoff note):** the runner does **not** pick up
> new `.py` code on its next cycle. `scripts/launch.py` imports `run_cycle` once
> and loops in-process (`CronRunner`), so the spawn-gate code only loads on a
> **restart**. Only `config/spawn-schedules.yaml` is re-read live. §6 restarts
> both processes — do not skip it, or the gate won't actually be enforced.

---

## 1. Pre-flight check

**Dir:** `C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules`

```powershell
# Are runner + dashboard still alive? (PIDs at handoff: runner 31304, dashboard 45112)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'launch.py|uvicorn' } |
  Select-Object ProcessId, CommandLine | Format-List
```

```powershell
# Dashboard responding?
Invoke-RestMethod http://127.0.0.1:8765/state | Out-Null; "dashboard OK"
```

```powershell
cd "C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules"
git status -s
git log --oneline master..HEAD
```

**What you should see:** 14 commits (`43a226b` … `719a8ed`). `git status -s` will
show modified `*.pyc` under `runner/.../__pycache__/` and a handful of untracked
`workspace/tasks/...` + `workspace/scheduler-state.json` files. **That is expected
runtime noise** — bytecode and task artifacts, none of it part of the branch's
source. There should be **no modified tracked source files**. If you see edits to
`runner/`, `dashboard/`, or `config/` source, stop and investigate before merging.

---

## 2. Review the changes

**Dir:** `C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules`

```powershell
git log --oneline --stat master..HEAD | more
```

Review the high-impact files in this order. One command per area.

```powershell
# The spawn-cadence gate — the heart of this branch (new, 376 lines)
git diff master..HEAD -- runner/scheduler/spawn_gate.py config/spawn-schedules.yaml
```
Look for: `spawn_allowed()` returns `(bool, reason)`; cooldown / `max_per_day` /
`quiet_hours` precedence in `_evaluate`; decisions append to
`spawn-decisions.jsonl` capped at 1000 lines; the only configured rule is
`by_task_type.prospect_research` (30-min interval, 40/day, 3-min jitter).

```powershell
# Sandboxed PoC runner (new, 220 lines) — security-sensitive
git diff master..HEAD -- runner/tools/poc_sandbox.py
```
Look for: slug regex confines work to `workspace/poc/<slug>/`; the `_POC_FORBIDDEN`
deny-list (network egress, registry, persistence, process-kill, credential theft,
`-EncodedCommand`); per-slug hard dollar meter refusing **before** spawn.

```powershell
# Runner wiring — where the gate plugs into the cycle
git diff master..HEAD -- runner/main.py runner/config.py runner/ledger/budget.py
```
Look for: gate consulted at the `create_task` chokepoint and in the planning-task
revival path; per-pod daily cap; `load_spawn_schedules` reads the YAML live.

```powershell
# Dashboard — new Spawn Gate + Opportunity panels
git diff master..HEAD -- dashboard/server.py dashboard/index.html
```
Look for: new `GET /api/spawn-gate` and `GET /api/opportunities` endpoints;
matching `Opportunities` and `Spawn Gate` tab buttons + render functions.

```powershell
# Opportunity tooling + synthesis
git diff master..HEAD -- runner/tools/opportunity.py scripts/opportunity_synthesis.py runner/scheduler/daily_jobs.py
```

```powershell
# Phase 5 spec (docs only — no code)
git diff master..HEAD -- docs/superpowers/specs/2026-05-28-prospector-phase5-pnl.md
```

---

## 3. Run the test suite

**Dir:** `C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules`

```powershell
cd "C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules"
python -m pytest -q
```

**Expected: `231 passed, 20 failed`.**

The 20 failures are **pre-existing / environmental** — they fail on `master` too and
are unrelated to this branch. 19 are in unchanged test files; 1 is a new test that
only needs an API key. Recognize them by file:

| File | Fails | Cause |
|------|-------|-------|
| `tests/runner/test_base.py` | 3 | pre-existing |
| `tests/runner/test_config.py` | 1 | pre-existing |
| `tests/runner/test_tony_bridge.py` | 3 | pre-existing |
| `tests/runner/test_tool_runner.py` | 1 | pre-existing |
| `tests/runner/test_tools_files.py` | 5 | pre-existing |
| `tests/runner/test_tools_web.py` | 2 | pre-existing |
| `tests/test_inbox_reader_interest.py` | 1 | pre-existing (heuristic drift) |
| `tests/test_web_research_captcha.py` | 3 | pre-existing (heuristic drift) |
| `tests/runner/test_budget_pods.py::test_agentbase_passes_pod` | 1 | **needs `OPENAI_API_KEY`** — passes with the key set |

**If the numbers don't match:** as long as all failures are in the files above,
you're fine. If a **new** file fails (especially anything under §3b), or the pass
count drops well below ~231, **do not merge** — re-run that file with `-x` and
read the traceback.

### 3b. Confirm the new Prospector tests are green (the real signal)

```powershell
python -m pytest `
  tests/runner/test_spawn_gate.py `
  tests/runner/test_spawn_gate_panel.py `
  tests/runner/test_poc_sandbox.py `
  tests/runner/test_opportunity_chain.py `
  tests/runner/test_opportunity_routing.py `
  tests/runner/test_opportunity_synthesis.py `
  tests/runner/test_opportunity_tools.py `
  tests/runner/test_daily_jobs.py `
  tests/runner/test_base_all_errored.py `
  tests/runner/test_vault_memory_guard.py -q
```

**Expected: `116 passed`.** This is the gate. If this is green, the branch logic is good.

---

## 4. Live-fire the spawn gate (BEFORE merging)

This proves the gate denies on cooldown end-to-end, **without** starting a second
runner (a second `uvicorn` on 8765 would collide with the live dashboard). It runs
fully **isolated** in a temp ledger — it writes nothing to the worktree or the live
app.

**Dir:** `C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules`

```powershell
cd "C:/Users/alexa/Downloads/aiocc-wt-spawn-schedules"
python -c @'
import tempfile, pathlib
from runner.scheduler import spawn_gate
tmp = pathlib.Path(tempfile.mkdtemp())
spawn_gate.LEDGER_DIR = tmp
spawn_gate.HISTORY_FILE = tmp / "spawn-history.json"
from runner.scheduler.spawn_gate import spawn_allowed, record_spawn, read_decisions
for i in range(3):
    ok, why = spawn_allowed("outreach_worker", "prospect_research")
    print(f"attempt {i}: allowed={ok}  {why}")
    if ok:
        record_spawn("outreach_worker", "prospect_research")
print("decisions logged:", len(read_decisions()))
'@
```

**Expected output:**
```
attempt 0: allowed=True
attempt 1: allowed=False  type:prospect_research cooldown active - next spawn allowed in ~30 min (...)
attempt 2: allowed=False  type:prospect_research cooldown active - next spawn allowed in ~30 min (...)
decisions logged: 3
```

First spawn allowed, the next two denied on cooldown, all three audited. If attempt
0 is denied, a `next_allowed` was already set in the temp dir — re-run (fresh temp
dir each time) and it will pass.

---

## 5. The merge

> **Coordinate first.** Other sessions are touching this repo (a GitHub-push
> session runs `git`, a CRM session edits `dashboard/`, a cleanup session edits
> root files). Make sure the push session is **idle** before you merge/push so you
> don't step on each other.

**Dir:** `C:/Users/alexa/Downloads/AI Operations Command Center`

```powershell
cd "C:/Users/alexa/Downloads/AI Operations Command Center"
git status -s
```
Runtime files (`workspace/...`, `.obsidian/...`, `dashboard-state.json`) will show
as dirty — that's the live app writing, and the branch doesn't touch them, so the
merge won't conflict. If you want a clean tree first: `git stash -u` (optional).

```powershell
git checkout master
git pull --ff-only        # in case the push session advanced origin/master
```

```powershell
git merge --no-ff feat/prospector-phases-1-4 -m "merge: Prospector Phases 1-4 + spawn-cadence gate + sandboxed PoC"
```
`--no-ff` keeps a merge commit, which the §8 rollback (`git revert -m 1`) needs.

```powershell
git log --oneline -3      # confirm the merge commit + that the 14 commits came in
git push
```

If `git pull --ff-only` errors (diverged), **stop** — the push session may have
rewritten history. Reconcile with that session before merging.

---

## 6. Restart procedure

After merge, **both** processes are still running the old in-memory code. Restart
them so the gate is actually enforced and the Spawn Gate tab appears. Cleanest path:
stop both, relaunch `launch.py` once (it starts the runner **and** a fresh dashboard).

**Dir:** `C:/Users/alexa/Downloads/AI Operations Command Center`

```powershell
# Find current PIDs (they may differ from 31304 / 45112 by now)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'launch.py|uvicorn' } |
  Select-Object ProcessId, CommandLine | Format-List
```

```powershell
# Stop both (substitute the PIDs you just saw)
Stop-Process -Id <RUNNER_PID>, <DASHBOARD_PID> -Force
```

```powershell
# Relaunch runner + dashboard together, detached, from the main repo
cd "C:/Users/alexa/Downloads/AI Operations Command Center"
Start-Process python -ArgumentList 'scripts/launch.py','--interval','900' `
  -WorkingDirectory "C:/Users/alexa/Downloads/AI Operations Command Center"
Start-Sleep -Seconds 6
```

**Verify the new endpoint is live:**
```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/spawn-gate | ConvertTo-Json -Depth 5
```
You want a JSON payload with `summary`, `keys` (including `type:prospect_research`),
and `recent`. A 404 means the old dashboard is still up — confirm the stop worked
and the relaunch ran from the **main repo** (not the worktree).

---

## 7. Smoke test (post-merge)

Open `http://127.0.0.1:8765` and click through:

- **Opportunities** tab — Opportunity Board renders (an empty table is fine), no
  console errors.
- **Spawn Gate** tab — shows `prospect_research` with its interval/cap and a
  status (ready / cooldown), plus a recent-decisions feed.

Then fire one real outreach cycle and confirm the gate logs a decision:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/trigger `
  -Body '{"pod":"outreach"}' -ContentType 'application/json'
Start-Sleep -Seconds 10
Get-Content "C:/Users/alexa/Downloads/AI Operations Command Center/workspace/ledger/spawn-decisions.jsonl" -Tail 5
```

You should see fresh JSON line(s) with `"task_type":"prospect_research"` and an
`allowed` field. (This runs a real cycle and spends a little budget — fine within
the $2/day cap, just don't loop it.)

---

## 8. Rollback plan

If anything misbehaves after merge:

**Dir:** `C:/Users/alexa/Downloads/AI Operations Command Center`

```powershell
cd "C:/Users/alexa/Downloads/AI Operations Command Center"
git log --oneline -5      # find the merge commit SHA
git revert -m 1 <MERGE_SHA>
```
Then restart (repeat §6: stop both PIDs, relaunch `launch.py`), and confirm:
```powershell
git log --oneline -3
Invoke-RestMethod http://127.0.0.1:8765/api/spawn-gate   # 404 again = reverted cleanly
git push
```
`-m 1` keeps `master`'s side and undoes the branch — that's why §5 used `--no-ff`.

---

## 9. Phase 5 prep

Spec: `docs/superpowers/specs/2026-05-28-prospector-phase5-pnl.md` (graduation,
revenue ledger, Stripe reconciliation, P&L panel). It goes through its own
spec→plan cycle before any code.

**Provider question is already answered in the spec:** **Stripe, read-only /
poll-based** (no webhook server in v1). The real human input still pending before
the plan phase:

- Provide a **Stripe test-mode** restricted key via `STRIPE_RESTRICTED_KEY` (env
  var, never a file — per the ROADMAP stop condition).
- Decide when to flip from **test mode → live** — that's a separate, second
  approval gate (`live_key_connect`), distinct from graduating a pod.

---

## 10. Pending decisions (waiting on you)

- **Strip frontmatter from `agents/learned_rules`?** — flagged during the memory
  audit; decide before the next learning-loop run.
- **Push `feat/prospector-phases-1-4` to GitHub?** — a separate session is handling
  the push; confirm whether it pushes the branch or only post-merge `master`.
- **CRM wiring choices** — the CRM session (editing `dashboard/`) flagged decisions;
  review its handoff before merging anything it produces on top of this.
- **Stripe test-mode key** for Phase 5 (see §9).
