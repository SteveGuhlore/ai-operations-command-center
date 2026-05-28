# Prospector — Opportunity Pod Design

**Date:** 2026-05-27
**Status:** Approved design, pending implementation plan
**Author:** brainstorming session (Stephen + Claude)

## 1. Goal

Add a new isolated agent + pod, **Prospector** (`opportunity_worker` / `opportunity_pod`), that autonomously discovers real AI-agent business ideas, scores them, writes build specs and sample deliverables, builds and grades sandboxed proof-of-concepts, and self-tunes nightly. It surfaces a ranked, evidence-backed shortlist of opportunities on the dashboard so the operator can decide which to graduate into real revenue pods.

Prospector ships behind its own pod and role and makes **no behavioral change** to the two active revenue pipelines (Easy Simple Sites outreach, Tony Stocks). The shared memory/learning layer is hardened as part of this work so all active agents benefit.

## 2. Scope decisions (locked)

| Decision | Choice |
|---|---|
| What to hunt | Any AI-agent business idea; `system_fit` is one scored dimension so system-runnable ideas float up while bigger operator plays still surface ("both, ranked together") |
| Memory/learning scope | Prospector's own layer **plus** shared-infra hardening that benefits every agent |
| Build scope | All four phases (P1–P4), sequenced |
| Model posture | Tiered: Gemini Flash for scouting volume, gemini-2.5-pro for deep-dive/scoring of top candidates |
| Human gate | None on P1–P4 — fully autonomous; the dashboard board is FYI only. Existing hard guardrails (no real external sends, no broker trades, global + pod budget stop) still bound everything |
| Pod budget | `$10/day` pod cap; `$2` per-PoC cap |
| Cadence | One `opportunity_scout` task dropped ~every 2 hours (configurable), isolated from Atlas; each run self-chains its follow-on phases |
| PoC sandbox | Metered real-tool access (existing tools/keys) within the per-PoC cap; no new accounts, no sends, no deploys; code confined to `workspace/poc/<slug>/` |
| Orchestration | Approach B (Prospector researches, Forge builds) with a swappable grading seam so upgrading to Approach C is a config change |

## 3. Orchestration (Approach B + C-seam)

`opportunity_worker` (Prospector) owns research, scoring, specs, samples, and grading. The existing `heavy_worker` (Forge) — currently idle — builds and runs PoCs. Phases are separate task types resolved by the existing `router.py` routing table.

**The C-seam:** grading is its own task type, `poc_grade`, resolved through the routing table. In B it routes back to `opportunity_worker`. To become Approach C later, add an `opportunity_evaluator` role and change the single routing line — the build→grade→learn contract and the verdict format are unchanged.

### Roles & wiring

- **New role `opportunity_worker`** (display **Prospector**): added to `config/agents.yaml`, `MODELS`, `ROLE_TOOLS`, `_ROLE_MD_FILES`, `VALID_AGENTS`.
- **New pod `opportunity_pod`**: pod-config entry + `create_task` pod enum; `$10/day` cap; assigned agents `opportunity_worker` + `heavy_worker`.
- **`heavy_worker` (Forge) gains** `code_runner` + `task_creator` in `ROLE_TOOLS` (additive only).

### Task types & routing

| task_type | routes to | model | phase |
|---|---|---|---|
| `opportunity_scout` | opportunity_worker | Flash | P1 |
| `opportunity_deepdive` | opportunity_worker | Pro | P1/P2 |
| `opportunity_spec` | opportunity_worker | Pro | P2 |
| `poc_build` | heavy_worker (Forge) | (Forge default) | P3 |
| `poc_grade` | opportunity_worker ← **C-seam** | Pro | P3 |

**Model tiering** is implemented as a small `TASK_MODEL_OVERRIDES` dict keyed by `task_type` that wins over the role default at the `model = MODELS.get(role_id, ...)` line in `run_task`.

## 4. Data model

### Vault layout
- `vault/opportunities/ledger.md` — master scored table, one row per idea (slug, composite, phase, status, last-updated). Read **first** every run (dedup + persistence), updated **after** — mirrors Tony's signal-ledger.
- `vault/opportunities/<slug>.md` — per-opportunity page: the six score dimensions, problem, who-pays, P2 build-spec, P2 sample deliverable, P3 PoC grade + reason, date-stamped history, Obsidian wikilinks.
- `vault/opportunities/_moc.md` — Map-of-Content hub note (matches the Obsidian cleanup plan).
- `workspace/poc/<slug>/` — sandboxed demo code, a fixture input, captured output, grade.

### Scoring schema (six dimensions, 0–10 each)

| dimension | meaning | weight |
|---|---|---|
| willingness_to_pay | who pays & how much | 0.25 |
| revenue_potential | ceiling if it works | 0.20 |
| problem_severity | how real/painful | 0.15 |
| buildability | inverse of effort | 0.15 |
| system_fit | can THIS system's agents/tools run it | 0.15 |
| novelty | non-slop, defensible | 0.10 |

`composite = (weighted sum) × 10` → 0–100. `system_fit` is meaningful but not dominant, so operator-only plays still surface.

### Auto-promotion thresholds (fully autonomous)
- composite **≥ 75** → auto-spawn `opportunity_spec` (Pro deep-dive + sample)
- re-scored with spec evidence, still **≥ 75** → auto-spawn `poc_build` (Forge)
- PoC graded **promising / weak / dead** + reason → written to page & ledger; promising ideas rise to the top of the board as the FYI shortlist.

### Forward-compatible fields (for Phase 5)
Ledger rows carry, from day one: `status` (incl. `graduated`), a `pod` link field, and **separate `est_*` vs `actual_*` fields** so a real measured number never overwrites an estimate.

## 5. The four-phase flow

```
Scout (Flash, 15-20 ideas) → quick-score → ledger rows + stub pages
  └─ ideas ≥75 → Deepdive+Spec (Pro) → re-score + build-spec + sample deliverable
       └─ still ≥75 → poc_build (Forge) → demo in workspace/poc/<slug>/, run on fixture (metered)
            └─ poc_grade (Prospector ← C-seam) → promising/weak/dead → ledger + page
                 └─ (nightly) P4 synthesis → penalize high-score/poor-demo → tune prompt
```

**Error handling:** budget cap stops the chain gracefully — entries stay at their current phase and resume next run; a failed/over-cap PoC build grades `dead` with the reason; dedup against the ledger prevents re-scouting the same idea.

## 6. Memory & learning layer

### Prospector's own memory
- `vault/agents/opportunity_worker/memory.md` (raw run log) + `learned_rules.md` (Sage-distilled) — auto-injected into its prompt by `load_agent_memory` once the role exists.
- Domain memory = the ledger + opportunity pages (its equivalent of Tony's per-ticker pages): the long-term record of ideas seen, what scored well, what demoed poorly.

### P4 — nightly learning loop
Rides the cross-platform daily hook (§7). Each night it reviews the day's new ledger entries + PoC grades and computes **score-vs-demo divergence** — ideas that scored ≥75 but graded weak/dead. It penalizes the patterns behind those misses, reinforces patterns that scored high *and* demoed promising, and tunes `agents/opportunity_worker.md` (same mechanism `improvement_loop` uses). Writes a note to `vault/learnings/<date>-opportunities.md`. This delivers Approach C's independent-grader bias-correction without a third always-on role: the nightly pass is a separate evaluation context from the scout.

### Shared-layer hardening (benefits every agent)
1. **Trigger fix** — the cross-platform daily hook (§7) makes nightly learning actually fire on Windows and the VPS.
2. **Active agents in the loop** — add `opportunity_worker` to `improvement_loop._AGENTS_TO_REVIEW`; verify the active-agents fix from the prior session is committed.
3. **No-op / false-success guard** — confirm `auto_write_task_memory`'s noop downgrade is solid and extend it so "all tool calls errored" logs as `failure`, not success.
4. **Sage learns Prospector** — add Prospector's memory to Sage's read list + rule distillation.
5. **Memory-graph backlinks** — Sage adds wikilink backlinks from each agent's `learned_rules.md` to the entities it references; Prospector's pages ↔ ledger ↔ rules linked.
6. **Cross-agent reuse** — Prospector's `system_fit` scoring reads other agents' `learned_rules` to judge whether the system can actually run an idea, making the shared knowledge graph a scoring input.

## 7. Cross-platform daily/interval hook (trigger fix)

The nightly `improvement_loop.py` is only triggered by a Linux-only systemd timer (`improvement-loop.timer`, 2 AM daily); on Windows nothing fires it, and `launch.py`'s `CronRunner` only calls `run_cycle()`. Weekly Sage has the same gap.

Fix: add a once-per-day check inside `run_cycle()` — "has the daily learning loop run today? if not and it's past the scheduled hour, run it once" (and the weekly Sage on Sundays). Cross-platform, no systemd/Task Scheduler dependency. Prospector's P4 rides the same hook. A sibling interval check in `run_cycle()` drops one `opportunity_scout` task every ~2 hours (configurable), isolated from Atlas's spawn logic.

## 8. Dashboard — Opportunity Board

A read-only panel at `:8765` matching the existing command-center aesthetic (dark neon palette via the existing CSS variables, `.panel` cards, the glowing budget-bar style). Pushed over the existing WebSocket. Answers four questions at a glance:

```
┌─ OPPORTUNITY BOARD ──────────────────────────────────────────────┐
│ SPENT TODAY    NEXT SCOUT   IDEAS   PROMISING   EST. PIPELINE      │
│ $3.40 / $10 ▓▓░░  in 1h12m    24       3        ~$2,800/mo (est)   │
├───────────────────────────────────────────────────────────────────┤
│ PIPELINE   Scouted 24 → Specced 6 → Built 3 → ◍ promising 3 ·      │
│            weak 2 · dead 1        (2 queued · 1 building now)      │
├───────────────────────────────────────────────────────────────────┤
│ #  IDEA                       SCORE  PHASE   POC      FIT  $run $est│
│ ┃1 ai-review-reply-agent       82●   graded  ◍promis  9▓  $0.04 $900│
│  2 receptionist-setup-svc      79●   built   ◍promis  6▓  $0.31 $1.2k│
│  3 lease-abstract-bot          76●   spec    —        8▓  ~$0.10  — │
│  4 etsy-tag-optimizer          71○   scouted —        7▓   —     — │
├───────────────────────────────────────────────────────────────────┤
│ ACTIVITY                                                          │
│ 15:12  graded ai-review-reply-agent → promising                    │
│ 15:10  Forge built PoC ($0.42)                                     │
│ 14:30  spec'd receptionist-setup-svc · re-score 79                 │
│ 14:02  scouted 18 ideas · 3 ≥75                                    │
└───────────────────────────────────────────────────────────────────┘
```

- **Has done** → pipeline funnel (counts by phase) + timestamped activity feed.
- **Will do** → "next scout" countdown + dim "queued / building now" counts.
- **Has spent** → header tile (`$spent / $10`, reusing the glowing budget bar; orange ≥70%, red ≥95%) + per-PoC `$run` column.
- **Will spend / make** → `$run` (est. build/run cost from the P2 spec) and `$est` (projected monthly revenue from `revenue_potential`).

**Honesty rule:** `$est` and "pipeline value" are always labeled estimates/hypotheses — Prospector's revenue is researched projection, never booked income. Real money appears only once a pod has graduated and logged actual revenue (§10).

Rows color-grade by score (green ≥75 / amber 60–74); promising PoCs get the green-glow left border; click-to-expand shows problem / who-pays / spec / sample / grade reason. Data sources: `ledger.md` + per-opportunity pages + the real budget ledger + the task queue.

## 9. Budget & safety invariants (hard-baked)

- `opportunity_pod` = `$10/day` in `budgets.yaml`; enforced by the existing `is_budget_exceeded` path — hard-stops like any pod, cannot starve outreach/Tony.
- Per-PoC `$2` cap tracked per slug; abort and grade `dead (budget)` if exceeded.
- PoC code confined to `workspace/poc/<slug>/`; `code_runner` with a subprocess timeout.
- Metered real-tool access only — no new external accounts, no sends, no deploys.
- Existing global guardrails (no broker trade, global budget stop) remain in force.
- Atlas's `_maybe_spawn_planning_task` is never touched; Prospector is triggered by its own interval hook.

## 10. Phase 5 — Graduation & Real P&L (forward-looking)

When the operator approves a promising PoC to scale, the idea **graduates**: it becomes a real revenue pod (like `local_outreach_pod`), its board row flips to `graduated`, and `$est` is replaced by a link to the pod's live P&L.

The system currently tracks real **spend** but no **revenue**. Phase 5 adds the missing half: a **revenue ledger** auto-populated by an approval-gated **payment-provider/affiliate API feed** (Stripe/PayPal/affiliate), surfaced as a per-pod P&L view (spend vs. revenue vs. net). The provider integration is an external/account action and stays behind the operator's approval.

Data hooks are baked in now (§4): `status: graduated`, the `pod` link, and separate `est_*`/`actual_*` fields so estimates and real numbers never collide. The P&L display and provider feed are built in Phase 5, after P1–P4 prove out.

## 11. Change surface

**New files**
- `agents/opportunity_worker.md` — Prospector prompt
- `runner/tools/opportunity.py` — `log_opportunity` + `grade_poc` tool specs/functions
- dashboard Opportunity Board panel (markup/JS in `dashboard/index.html`, data in `dashboard/server.py`)
- `vault/opportunities/` seed (`ledger.md`, `_moc.md`)
- tests

**Edited (all additive / careful)**
- `config/agents.yaml` — `opportunity_worker` role
- `config/budgets.yaml` — `opportunity_pod` cap
- `runner/main.py` — `MODELS`, `TASK_MODEL_OVERRIDES`, `ROLE_TOOLS` (incl. Forge +`code_runner`/+`task_creator`), daily learning hook + scout interval hook
- `runner/agents/prompts.py` — `_ROLE_MD_FILES`
- `runner/tools/task_creator.py` — `VALID_AGENTS` + pod enum
- `scripts/improvement_loop.py` — `_AGENTS_TO_REVIEW` + opportunity synthesis, false-success extension
- `runner/tools/vault_memory.py` — false-success guard hardening
- `agents/librarian.md` — Sage reads Prospector + adds backlinks

## 12. Testing

- Unit: new-task-type routing → correct roles; composite-score math; ledger dedup; budget-cap stop (pod + per-PoC); no-op/false-success guard.
- Dry-run: a mocked scout run produces ledger rows + page stubs + chained spec/build/grade tasks; board renders from the ledger.
- Isolation check: confirm Atlas still only spawns Pitch and that outreach/Tony behavior is unchanged.

## 13. Build order

1. **P1** — role + pod + config wiring, `opportunity_scout`, scoring, ledger, `log_opportunity`, Opportunity Board panel, scout interval hook.
2. **Shared hardening** — cross-platform daily hook, false-success guard, active agents in the loop.
3. **P2** — `opportunity_deepdive` + `opportunity_spec` (Pro), build-spec + sample deliverable, model tiering.
4. **P3** — Forge `poc_build` (sandbox, metered, per-PoC cap), `poc_grade` + `grade_poc` tool (C-seam).
5. **P4** — nightly opportunity synthesis + prompt self-tuning; Sage learns Prospector + backlinks.
6. **Phase 5 (later)** — graduation lifecycle, revenue ledger, provider integration, real P&L panel.
