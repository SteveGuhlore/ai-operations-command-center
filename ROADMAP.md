# Roadmap

## Current integrated foundation

The AI Operations Command Center now has a generic local foundation for:

- task lifecycle folders
- lock files
- run logs
- batch reports
- dry-run worker simulation
- doctor and validation scripts
- generic reusable agent roles
- model-mapping examples
- tool registry examples
- guardrail examples
- budget examples
- schedule examples
- revenue pod examples
- visual dashboard and Star Office UI bridge planning
- shortcuts
- worker playbooks
- memory structure
- evaluation structure
- tool mastery structure
- handoff documentation

## What is working now

- `doctor.ps1` validates the core foundation state
- task validation works across all status folders
- sample tasks can be reset and re-run safely
- dry-run simulates worker pickup, lock creation, movement to `review`, run logs, and report generation
- agent, tool, guardrail, budget, and revenue pod configs all validate
- role IDs and display names are documented and consistent
- dashboard integration is planned as a read-only status layer
- shortcut helpers exist for local dashboard launch flow
- playbooks, memory, evaluation, and tool mastery structures are documented

## What is intentionally stubbed

- real project connection
- real model provider adapters
- API-backed execution
- real worker launch
- dashboard transport bridge
- recurring daemon runtime
- publishing, purchasing, billing, or account actions
- any autonomous external action

## Phase roadmap

### Phase 0 - Foundation Complete

- task lifecycle folders
- locks
- logs
- dry-run workers
- doctor/validators
- generic agent roles
- model mapping
- tools registry
- guardrails
- budgets
- schedules
- revenue pods
- visual dashboard strategy
- handoff docs

Status: complete for the current local foundation.

### Phase 1 - Project Profile Connection

- connect first real project through profile
- collect selected context
- create project-specific tasks
- keep command center as source of truth

Goal: prove the foundation can supervise one real project without losing the generic abstractions.

### Phase 2 - Real Worker Adapter

- provider-agnostic worker interface
- model routing
- real APIs
- no keys in files
- dry-run vs real-run modes
- retries/escalation

Goal: add real execution adapters while preserving the same role IDs, approvals, and validation boundaries.

### Phase 3 - Dashboard Bridge

- Star Office UI or other visual shell
- `dashboard-push.ps1`
- read-only status display
- agent/task/run status

Goal: expose command-center state visually without letting the dashboard become the system of record.

### Phase 4 - Scheduler / Daemon

- heartbeat
- recurring queue scan
- crash recovery
- daily reports
- budget enforcement
- stop/shutdown controls

Goal: make the foundation resilient for recurring operation without enabling unsafe autonomy.

### Phase 5 - Revenue Pod Activation

- activate one pod at a time
- Etsy/Digital Products/Lead Gen/etc.
- publish queue
- cost tracking
- performance tracking
- platform publishing
- revenue tracking

Goal: begin monetizable workflows carefully, with approval gates and one pod at a time.

### Phase 6 - 24/7 Operations

- always-on workers
- budget caps
- queue rotation
- monitoring
- weekly optimization

Goal: move from supervised batch operation to reliable continuous operation with strong controls.

### Phase 7 - Advanced Autonomy

- Atlas creates tasks
- Atlas routes to agents
- Guard/Ledger enforce policy and budget
- limited auto-publish only after proven performance

Goal: allow narrow, well-proven autonomy only after repeated evidence that policy, budget, and quality controls hold.

## Agent Intelligence & Learning Roadmap

This roadmap section is mostly about operational conditioning, memory, evaluation, and routing rather than frontier-model training.

Real fine-tuning is optional and much later. Prompt quality, memory, evaluation, and routing matter more initially than custom model training.

### Phase A - Worker Playbooks

- role playbooks
- quality standards
- escalation rules
- allowed/forbidden behavior
- output formatting

Goal: make each role more consistent before adding more autonomy.

### Phase B - Memory System

- successful outputs
- failed outputs
- retry history
- pod performance
- reusable context bundles
- shared knowledge structure

Goal: preserve useful operational memory so the system can improve without re-learning the same lessons repeatedly.

### Phase C - Evaluation System

- output scoring
- quality reviews
- bug/failure tracking
- pod performance metrics
- model comparison metrics
- retry effectiveness

Goal: measure what is working well and what is not before changing routing or model choices.

### Phase D - Tool Mastery

- specialized tool usage guides
- platform-specific workflows
- content generation standards
- coding standards
- debugging standards

Goal: improve how agents use tools and workflows, not just which model is selected.

### Phase E - Revenue Optimization

- profitable task detection
- low-performing pod detection
- cost vs revenue scoring
- content performance tracking
- successful product patterns

Goal: identify which pods and workflows are worth more investment and which should be reduced or paused.

### Phase F - Atlas Orchestration Intelligence

- task prioritization
- pod prioritization
- worker routing improvements
- retry routing
- model selection improvements

Goal: help Atlas make better routing and prioritization decisions using accumulated operational evidence.

### Phase G - Long-Term Learning

- dataset collection
- memory compression
- future fine-tuning datasets
- routing model ideas
- evaluation model ideas

Goal: prepare long-term learning assets only after the earlier memory, evaluation, and routing layers are proven useful.

## Opportunity Pod — "Prospector" (planned, build isolated)

A new agent + pod that researches real AI-agent business ideas, proves them out, and surfaces ranked opportunities for the operator to scale. Learning loop: scored opportunity ledger + nightly synthesis (same pattern as `improvement_loop.py` / Sage the librarian).

**Isolation guarantee (non-negotiable):** every phase ships behind its own pod (`opportunity_pod`) and agent role (`opportunity_worker`). It reuses existing tools but adds NO changes to outreach or Tony Stocks pipelines. PoC code runs only in `workspace/poc/<slug>/`. Hard per-opportunity and per-day budget caps enforced via existing `budget.py`. No live spend, no real external sends, no deploys without an explicit operator `NEEDS_HUMAN` gate.

### Phase P1 - Scout + Scored Ledger (lowest risk, build first)
- New `opportunity_worker` (Gemini Flash) researches concrete, non-slop AI-agent business ideas
- Writes scored entries to `vault/opportunities/ledger.md` (problem, who pays, build effort, revenue potential, novelty, composite score)
- New read-only "Opportunity Board" panel on the dashboard
- No code execution. Near-zero blast radius.

### Phase P2 - Written Spec + Sample Output
- For top-scored ideas, agent writes a build spec (inputs/outputs, tools reused, cost-per-run estimate) + a hand-generated sample deliverable
- Still no code execution

### Phase P3 - Sandboxed PoC Build (the autonomous "build it" capability)
- Agent assembles a runnable demo in `workspace/poc/<slug>/` using `code_runner` (sandboxed) + the `builder` agent for any landing page
- Runs the demo against ONE real sample input, captures output, self-grades promising/weak/dead
- Mandatory: per-PoC budget cap, sandbox confinement, NEEDS_HUMAN gate before anything external

### Phase P4 - Nightly Learning Loop
- Nightly synthesis reviews the day's opportunities + PoC results and refines `opportunity_worker`'s own prompt (penalize patterns that score high but demo poorly, weight patterns that convert)
- Mirrors existing improvement-loop shape; writes to `vault/learnings/`

## Memory Layer Hardening (near-term, supports learning)

Findings after a few days of live running — concrete gaps to close:
- **`improvement_loop.py` ignores the only active agents.** `_AGENTS_TO_REVIEW` covers manager + 4 dormant pods but NOT `outreach_worker` or `market_research_worker`. Add the active agents; drop/deprioritize dormant ones.
- **Stale learned rule is actively misleading outreach.** `vault/agents/outreach_worker/learned_rules.md` (distilled 2026-05-25) still says "web_research → CAPTCHA → call queue," which contradicts the resolved-CAPTCHA standing directive. Re-run Sage or correct the rule so outreach stops being taught the obsolete lesson.
- **False-success pollution.** `auto_write_task_memory` logged the hallucinated Tony run as "success." No-op/empty runs (no tool calls) should log as failure or be skipped, so agents don't learn that doing nothing wins.
- **Obsidian graph:** vault knowledge (tickers/sectors/setups) is already wikilinked, but `vault/agents/*` memory is siloed. Add backlinks so learned rules connect to the entities they reference.

## Obsidian Cleanup Plan (planned, NO file moves)

The vault is already organized by domain (`vault/tickers`, `vault/tony-stocks`, `vault/outreach`, `vault/agents/<role>`). Folder paths are hardcoded across the code (`load_agent_memory`, Tony's prompt, etc.), so **physically moving vault folders would break the running system — do NOT do it.** Improve the graph instead, via links/tags, which is zero-risk.

**Step 1 — Map-of-Content (MOC) hub notes (no file moves):**
- `vault/outreach/_moc.md` — links all outreach files (crm, outreach memory, learned rules)
- `vault/tony-stocks/_moc.md` — links tickers, sectors, setups, signal-ledger, watchlist
- `vault/agents/_moc.md` — links each agent's memory + learned_rules (Forge/heavy_worker, Scout/debug_worker, etc.)
- Each MOC uses wikilinks so Obsidian graph view clusters by domain.

**Step 2 — Tags:** add frontmatter tags (`#outreach`, `#tony`, `#forge`, `#agent-memory`) to existing notes so they group without moving.

**Step 3 — Connect siloed agent memory:** add backlinks from `vault/agents/<role>/learned_rules.md` to the entities they reference (e.g. outreach rules → `[[crm]]`).

**Step 4 — Project ROOT cleanup (separate, verify-first):** the project root has loose notes/canvases (`CRM.md`, `HANDOFF.md`, `START_HERE.md`, `SESSION_SUMMARY.md`, `*.canvas`, stray dated `.md`, a `.mp4`). Move into a `notes/` or `docs/` folder ONLY after grepping each filename to confirm no code references it. Low-but-nonzero risk — check before moving.

## Stop conditions

- Stop if `doctor.ps1` fails.
- Stop if any validator fails.
- Stop if tasks remain stuck in `in_progress`.
- Stop if locks remain after dry-run or future worker runs.
- Stop if any step requires credentials in files.
- Stop if any step implies external posting, spending, purchases, or real account actions without explicit approval.
- Stop if a future integration tries to bypass the command center as source of truth.

## Next recommended build step

Next recommended build step: **Phase 1 - Project Profile Connection**

Why:

- the generic foundation is already broad enough
- the next highest-value proof is connecting one real project profile safely
- it tests task creation, selected context loading, and source-of-truth discipline without requiring real worker APIs yet
