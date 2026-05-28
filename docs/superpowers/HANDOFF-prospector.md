# Session Handoff — Build Prospector

**For the next (fresh) session.** Design + planning are done and committed. Your job: execute the plan. No code has been written yet (plan-first rule honored).

## Start here (read in order)
1. `CLAUDE.md` — project engineering standards + safety rules (plan-first, two hard stops).
2. `docs/superpowers/specs/2026-05-27-prospector-design.md` — the approved design.
3. `docs/superpowers/plans/2026-05-27-prospector.md` — the 15-task TDD implementation plan. This is your work queue.

## What you're building
Prospector (`opportunity_worker`) + `opportunity_pod`: an isolated, autonomous pipeline that scouts AI-agent business ideas, scores them, writes specs + samples, builds + grades sandboxed PoCs, and self-tunes nightly. Plus shared learning-layer hardening that fixes nightly learning for ALL agents. Full rationale is in the spec.

## How to execute
Use the **superpowers:subagent-driven-development** skill — one fresh subagent per task, review between tasks. Work tasks 1→15 in order. Each task is bite-sized TDD (write failing test → run → implement → run → commit). Do NOT skip the test-first steps.

## Hard constraints (do not violate)
- **Isolation:** never modify Atlas's `_maybe_spawn_planning_task` logic or the outreach/Tony pipelines. Prospector ships entirely behind its own pod/role. Task 15 Step 2 verifies this.
- **Budgets:** `opportunity_pod` = $10/day, $2/PoC. Global guardrails (no real external sends, no broker trades, budget stop) still apply.
- **PoC sandbox:** PoC code runs only under `workspace/poc/<slug>/` via `poc_runner` (cwd-confined). No real sends/signups/deploys.

## Efficiency (operator priority)
Model selection is **config-driven per phase** — see the `task_models:` block added to `config/agents.yaml` in Task 4. Each phase auto-uses its most efficient model every run (Flash for scout/spec/grade, Pro only for deep-dive of top candidates). To tune cost later, edit that YAML block and restart the runner — no code change. Forge's PoC build stays on its role default (kimi-k2.5, cheap long-generation).

## Known limitations (documented in the plan, not bugs)
- Per-PoC $2 cap is operationally bounded (pod cap + prompt guidance), not a hard mid-run cutoff — the runner only checks budget between tasks. The `per_poc_limit_usd` config value exists for future mid-run enforcement.
- True network isolation for PoCs isn't enforced on Windows; the sandbox relies on cwd confinement + the forbidden-pattern filter + budget + prompt rules.

## Phase 5 (later, do NOT build now)
Graduation + real P&L (approval-gated payment-provider integration) is deferred to its own spec/plan once P1–P4 prove out. The ledger already carries `status`/`pod`/`est_rev_mo` hooks so it isn't blocked.

## Done definition
All 15 tasks committed, `pytest -q` green, the Opportunity Board renders at :8765, and the Atlas-isolation check (Task 15 Step 2) prints `True`.
