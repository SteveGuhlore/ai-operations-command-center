# Multi-model audit — AI Ops Command Center + Tony-Stocks

**Run:** 2026-06-17 · **Models:** Claude Opus 4.8 (arbiter) + Codex gpt-5.4 (high reasoning) + Gemini 2.5-pro
**Mode:** aggressive auto-fix on isolated branch `review/autofix-2026-06-17` (both repos), strict TDD test gate.
**Base SHAs:** AI Ops `350d8f9` · Tony `5d3980c` (branch feat/kinetic-dashboard)

## Test baseline
- Tony-Stocks: 1257 passed / 0 failed → after fixes **1264 passed**.
- AI Ops: 947 passed / **4 pre-existing failures** (quarantined per CLAUDE.md) → after fixes **969 passed**, same 4.
  - `test_eval_harness::test_harness_reproduces_live_scorecard_baseline`
  - `test_research_wave::test_wave_enqueues_once_and_dedups`
  - `test_stress_round2::test_reaper_reaps_task_with_dead_owner`
  - `test_tony_enrichment_blocks::test_lessons_block_empty_without_data`

## Scope reviewed (3-model debate) so far
Execution path (Tony), risk-guard ledger (AI Ops), FastAPI control/data surface (Tony).
**Not yet reviewed:** signal/scoring logic, AI Ops dashboard server, cross-repo bridge, AI Ops `alpaca_paper.py` (1802 lines), Tony dashboard-web (TSX).

---

## FIXED & committed (test-gated)

| # | Repo | Severity | Finding | Models | Fix |
|---|------|----------|---------|--------|-----|
| 1 | AI Ops | high | `tony_live_guard`: `TONY_LIVE_ENABLED='0'/'false'` satisfied opt-in (any non-empty string truthy) | Codex | require explicit truthy token |
| 2 | AI Ops | med | `tony_live_guard`: NaN win rate slips past `< MIN_WIN_RATE` | Codex | reject non-finite |
| 3 | AI Ops | high | `budget`: negative/non-finite spend lowers meter, bypasses cap | Codex | `_clean_cost` clamp |
| 4 | AI Ops | **critical→high** | `drawdown_breaker`: corrupt/unreadable ledger or equity file read as `[]` → breaker disengages | Codex+Gemini | distinguish missing (cold start) vs corrupt (halt) |
| 5 | Tony | med | `controls.py`: request `symbol` interpolated into kill-file path (traversal) | Gemini | strict ticker regex → 400 |
| 6 | Tony | med | `vault.py /insights`: unbounded `limit` (resource exhaustion) | Codex+Gemini | clamp [1,100] |
| 7 | Tony | low→med | `order_router.size_position`: qty explosion when `(entry-stop)` tiny & max_notional=0 | Codex+Gemini | no-leverage equity cap |

Commits: AI Ops `de30504`, Tony `4918474`.

Severity note on #4: real-world impact is bounded because the breaker is gated behind `TONY_BREAKER_ENABLED` (off by default) and the consumer also swallows exceptions — the models couldn't see that gating (out of bundle), so I downgraded critical→high. Still a genuine fail-open in a safety device.

---

## NEEDS HUMAN DECISION (not auto-applied — by design)

| Finding | Repo | Why not auto-fixed |
|---|------|--------------------|
| Unauthenticated control plane: `_pin_ok` returns True when `DASHBOARD_ACTION_PIN` unset; `_origin_allowed` True when no Origin header | Tony | Flipping to fail-closed would lock the operator out of the local single-operator dashboard unless they set a PIN. **Behavior change — your call.** Recommend: require PIN when `ENV_ROLE=prod`, keep open for local dev. |
| `get_offhours_cap()` returns `inf` (uncapped) by default | AI Ops | **Intentional** per docstring ("token-maxx the research"). Flagged by both models but it's a deliberate design choice. |
| `decision_audit` fail-open (drops record, continues) | AI Ops | Intentional ("audit failure must never break the cycle"). Making it gate trading is a policy decision. |
| Budget/runway/audit RMW races (no file lock) in a multi-agent system | AI Ops | Real, but a correct cross-process lock + atomic write on Windows is a structural change worth reviewing, not blind-patching. |
| `cluster_risk`: unknown ticker → 'other' → bypasses correlation cap | AI Ops | Real (universe is expanding). Fix = assign unmapped symbols to a conservative default cluster — changes risk behavior; recommend review. |
| `runway`: deleting `runway.json` revives an expired pod | AI Ops | Needs a durable-start design decision. |
| `account_mode`: live isolation compares API key but not secret | AI Ops | Low; only matters at live cutover. |

---

## DOWNGRADED after full-repo arbitration (over-flagged in isolation)
- **Duplicate entry orders** (Tony, both flagged HIGH/CRITICAL): FALSE POSITIVE. Models assumed `open_symbols` came from `broker.list_positions()` (filled only); actual `paper_engine._portfolio_state` builds it from the repo, which records orders at submit (before fill) → pending orders ARE deduped.
- **Missing buying-power gate** (Tony): bounded by `max_notional_per_position` default 5000 + the new equity cap. Low real impact on a paper cash account.
- **Bracket entry is a market order** (Tony): by design (market entry); slippage note retained but not a bug.

This is the core value of the orchestrator pass: two of the loudest model findings dissolve once you read the wiring they couldn't see.
