# Design — Off-Hours Self-Learning Research Rounds

**Date:** 2026-06-06 · **Status:** approved (design), implementation pending
**Builds on:** `2026-06-06-tony-off-market-research-engine-design.md` (Off-Market Research Engine, live on `master`).

## Problem
The Off-Market Research Engine stages **one** full wave per upcoming open (N ticker deep-dives + 6
synthesis tasks, incl. a single `tony_self_review`), de-duped by `staged_for == open_date`. That wave
finishes in ~3h. Over a weekend Tony then **idles ~57h**. The operator wants the idle window filled
with *genuine new, deeper research* — led by deeper/iterative self-learning — **without** padding the
wave, adding an interval/delay, or capping spend.

## Goal & non-goals
- **Goal:** after the main wave drains, stage successive **rounds** of genuinely-new, deeper research,
  led by a self-learning battery that exploits Tony's already-built but under-used analytics.
- **Non-goals (explicit operator constraints):** do not stretch/pad the existing ~3h wave; do not add
  an interval/delay; do not add a dollar cap (the off-hours lane stays uncapped); do not re-run studies
  just to fill time. Finite genuine research, then idle is acceptable.

## Key insight from the research
Tony already has three self-learning analytics that the single `tony_self_review` barely uses
(`runner/ledger/tony_scorecard.py`): `discover_edges()` (evidence-tag → win-rate edges),
`calibration` in `compute_record()` (actual win-rate per `confidence` bucket), and
`sizing_attribution()` (picking- vs sizing-alpha). Combined with `workspace/tony-realized.json` (real
stop-outs/wins) and the verdict/outcome history, this is **cheap, compounding, mostly-no-web-search**
work — the right thing to lead with.

## Architecture
New function `maybe_stage_research_followups(now)` in `runner/bridge/research_wave.py`, called in
`runner/main.py`'s idle branch **immediately after** `maybe_stage_research_wave()`.

**Gate (all required):**
1. `market_session(now) == "closed"`.
2. The main wave for the upcoming open is already staged (`state["staged_for"] == open_date`).
3. **No outstanding `TONY-RW-*` task** in `workspace/tasks/todo/` **or** `.../in_progress/` — i.e. the
   prior batch has fully drained. This paces rounds by *completion*, not a timer (mirrors the existing
   two-folder check in `main.py:_pitch_is_alive`).

When the gate passes, stage the next round from an ordered list and bump
`state["rounds_done"][open_date]`. When `rounds_done == len(ROUNDS)` for that open, **no-op (idle)**.
State lives in the existing `workspace/research-wave-state.json`; `rounds_done` is keyed per open_date
so a new open resets the sequence.

### Rounds (ordered, one staged per drain)
- **Round 1 — Self-Learning Battery (lead).** Four distinct, evidence-driven study tasks
  (`assigned_agent: market_research_worker`, `pod: stock_research_pod`):
  1. **Calibration study** (`tony_calibration_study`) — read `compute_record().calibration`; does
     `confidence: high` actually beat `low`? Write the finding + a concrete adjustment to
     `vault/agents/market_research_worker/learned_rules.md`.
  2. **Edge mining + back-test** (`tony_edge_mining`) — run `discover_edges`, take the strongest and
     weakest evidence tags, sanity-check against history, codify into `vault/tony-stocks/pattern-library.md`.
  3. **Realized post-mortem** (`tony_realized_postmortem`) — walk every loss in
     `workspace/tony-realized.json`, tag each failure mode, aggregate the recurring ones into lessons.
  4. **Re-grade as resolved** (`tony_regrade`) — re-check picks whose outcomes have now resolved; update
     the record's lessons and any thesis that aged badly.
- **Round 2 — Deepen top-conviction names** (`tony_conviction_deepdive`) — for the top-N from
  `workspace/research-queue.json`: pre-mortem + thesis stress-test + competitor/supply-chain read.
- **Round 3 — Broaden** (`tony_broaden_scan`) — cross-asset / macro / sector + beyond-scanner-universe
  idea scans, recording fresh candidates with the `tony_ideas` tool.
- **Exhausted → idle.**

## Data flow
Idle cycle → `maybe_stage_research_wave` (round 0, unchanged) → `maybe_stage_research_followups`
(stages round k+1 only once round k has drained) → tasks run via the normal dispatcher (routed by
`assigned_agent`, instructed by the task body; no new runtime personas) → outputs land in
`done/`, vault files, and `research-queue.json`. The open-re-check (`scripts/preopen_reset.py`) and the
closed-market entry gate are untouched.

## Error handling
Fail-soft like `maybe_stage_research_wave`: the `main.py` caller wraps it in try/except and logs a
warning; a bad state file degrades to "stage round 1". No-op (not error) when the gate fails. Round
staging is idempotent within a round via the same drain gate (re-entry before drain stages nothing).

## Testing (`tests/runner/test_research_wave.py`, extended)
- Gate: no follow-up while the main wave's `TONY-RW-*` tasks are still in todo/in_progress.
- Ordering: after round 0 drains, round 1 stages exactly the four self-learning tasks; after round 1
  drains, round 2; then round 3.
- Dedup: re-entering a closed window before the current round drains stages nothing.
- Exhaustion: after round 3 drains, no further tasks; `rounds_done[open_date]` caps at `len(ROUNDS)`.
- Reset: a different open_date restarts the sequence at round 1.
- Market open / wave-not-yet-staged → no-op.

## Ops
Runner restart required after the edit (module caching — see the engine handoff §4). Off-hours lane
stays uncapped by default (`get_offhours_cap()` → ∞ unless `TONY_OFFHOURS_BUDGET_USD` set).
