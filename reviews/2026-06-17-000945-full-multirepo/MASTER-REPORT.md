# MASTER multi-model audit — AI Ops Command Center + Tony-Stocks

**Date:** 2026-06-17 · **Models:** Claude Opus 4.8 (arbiter) · Codex gpt-5.4 (high reasoning) · Gemini 2.5-pro
**Mode:** report + aggressive auto-fix on isolated branches, every fix TDD/validation-gated.

## Branches & commits (15 fixes)
| Repo | Branch | Commits |
|---|---|---|
| AI Ops | `review/autofix-2026-06-17` | `de30504` ledger fail-open · `54e1921` account-mode secret · `3472aef` atomic writes (B4) · `cb4e63e` dashboard slug (XSS+traversal) |
| Tony | `review/autofix-2026-06-17` | `4918474` api/router fixes |
| Tony | `auto/multi-review-sweep` → `auto/mr` (off ^) | `fac3cc5` config · `066ef17` control-path+MiniLine · `df45884` prod-PIN (B2) · `972f1ad` control wiring (B1) |

**`auto/mr` is the superset branch** — it contains every Tony commit above. The full loop sweep (`--target .`) runs on it.

## Test baselines → after
- Tony Python: 1257 → **1264 pass**, 0 fail.
- Tony dashboard-web (vitest): **24 pass**.
- AI Ops Python: 947 pass / **4 pre-existing reds** (quarantined) → **969 pass**, same 4.

---

## A. FIXED & committed (10 issues, all test-gated)

### AI Ops — risk-guard ledger (`de30504`)
1. **[high]** `tony_live_guard`: `TONY_LIVE_ENABLED='0'/'false'` satisfied the opt-in (any non-empty string was truthy). → explicit truthy token required.
2. **[med]** `tony_live_guard`: NaN win-rate slipped past `< MIN_WIN_RATE`. → reject non-finite.
3. **[high]** `budget`: negative/non-finite `cost_usd` lowered the meter → cap bypass. → `_clean_cost` clamp.
4. **[high]** `drawdown_breaker`: a corrupt/unreadable ledger or equity file read as `[]` → breaker disengaged. → distinguish missing (cold start, allow) vs corrupt (halt); returns a halted dict so the caller's exception fallback can't re-open it.

### Tony — API + router (`4918474`)
5. **[med]** `controls.py`: request `symbol` interpolated into kill-file paths (`FLATTEN_<symbol>`) → traversal. → strict ticker regex, HTTP 400 on bad input.
6. **[med]** `vault.py /insights`: unbounded `limit` → resource exhaustion. → clamp [1,100].
7. **[low→med]** `order_router.size_position`: tiny `(entry-stop)` + disabled max_notional → qty explosion. → no-leverage equity cap.

### Tony — dashboard-web (`066ef17`)
8. **[high]** `lib/api.ts`: `api.control.*` posted to `/api/control/<x>` (singular) but backend serves `/api/controls/<x>` (plural). Every control call would 404. → path corrected. (Buttons stay inert — see queue B1.)
9. **[med]** `MiniLine`: empty-state guard counted total points, so two 1-point series rendered a blank SVG. → require ≥1 drawable series.

(+ regression tests counted as fix #10's worth across both suites.)

---

## B. NEEDS YOUR DECISION (not auto-applied — money-adjacent, behavior-changing, or by-design)

**B1. Dashboard control buttons are inert AND money-adjacent.** `SystemView.tsx` / `PaperBookView.tsx` pass `onConfirm: () => {}` for Stop-watch, Pause-paper, **Flatten-all**, Trigger-scan. The API client now points at the right path (fix #8), but wiring `onConfirm` to actually call `api.control.flattenAll(...)` makes real money actions fire. **Recommend you approve before I wire it** (and per repo `AGENTS.md`, this Next.js is non-standard — I'll read its bundled docs first).

**B2. Dashboard auth fail-open (backend).** `controls._pin_ok` returns True when `DASHBOARD_ACTION_PIN` unset; `_origin_allowed` True when no Origin header → a curl client on the network can hit controls on a PIN-less prod instance. **Recommend:** require PIN when `ENV_ROLE=prod`, keep open for local dev. Behavior change → your call.

**B3. `cluster_risk`:** unknown ticker → `'other'` → bypasses the correlation cap. Real (universe is expanding). Fix changes risk behavior (assign unmapped → conservative default cluster).

**B4. RMW races (no file lock)** in `budget`, `runway`, `decision_audit` — real in a multi-agent system; correct cross-process locking on Windows is structural.

**B5. `runway`:** deleting `runway.json` revives an expired pod (needs durable-start design).

**B6. `account_mode`:** live isolation compares API key but not secret (low; only matters at live cutover) — safe to fix.

**By design (flagged, NOT bugs):** `get_offhours_cap()` returns `inf` ("token-maxx the research"); `decision_audit` fail-open ("must never break the cycle"); frontend PIN length-check (server is authoritative).

---

## C. DOWNGRADED after full-repo arbitration (models over-flagged in isolation)
- **Duplicate entry orders** (Tony — Codex+Gemini both CRITICAL/HIGH): **false positive.** `paper_engine._portfolio_state` builds `open_symbols` from the repo, which records orders at submit (before fill) → pending IS deduped.
- **Missing buying-power gate** (Tony): bounded by `max_notional` default 5000 + the new equity cap.
- **Bracket = market order** (Tony): by design.
- **Frontend sweep "convergence"**: the loop reported converged in round 1, but only because Claude/Gemini headless runs returned 0 parseable findings; Codex's 6 real findings were salvaged and arbitrated here (→ fixes #8, #9 + queue B1).

---

## D. NOT YET REVIEWED (next pass)
Signal/scoring/sizing logic (Tony `data/`, `analytics/`) · AI Ops dashboard `server.py`/`tony_routes.py`/`watcher.py` · cross-repo bridge (`tony_bridge`, `research_wave`) · AI Ops `alpaca_paper.py` (1802 lines) · most of Tony `dashboard-web` (non-component lib/app).

**Meta-lesson:** multi-model *agreement* is not truth — two of the loudest consensus findings dissolved under full-repo context. The value is an arbiter reading the whole graph, not a vote.

---

## ADDENDUM (round 2 — additional fixes & decisions)

### Now fixed (moved out of the queue)
- **B2 prod-PIN** (`df45884`): `_pin_ok` fails closed when `ENV_ROLE=prod` and no PIN set. ⚠️ **deploying to the VM requires setting `DASHBOARD_ACTION_PIN`** or controls 403.
- **B1 control wiring** (`972f1ad`): the dashboard buttons (Stop-watch/Pause/Flatten-all/Trigger-scan) now actually call `api.control.*` with PIN + toasts. ⚠️ **needs manual verification against a running dashboard+backend** — I couldn't exercise the live click→API flow.
- **B4 atomic writes** (`3472aef`): budget + runway state now write-temp+`os.replace` (corruption-safe). Full cross-process lock = remaining follow-up.
- **B6 account-mode** (`54e1921`): live isolation now checks the secret too, not just the key.
- **A-DASH slug** (`cb4e63e`): landing-slug path traversal + reflected XSS fixed via allowlist.

### Deliberately NOT changed (documented design tradeoffs — naive fix is worse)
- **B3 cluster 'other'**: author chose not to pool unknowns (would false-block uncorrelated buys). Real remediation = expand ticker map / dynamic sector lookup.
- **B5 runway revive-on-missing**: deliberately fails to ALIVE so a bug can't brick the pod (grace deadline still bounds it).
- **off-hours infinite budget**, **decision_audit fail-open**: both documented intentional.

### AI Ops dashboard server — reviewed (Codex high + Gemini 2.5-pro, both converged)
- **CRITICAL (queued): no auth on state-changing endpoints** — `/api/trigger`, `/api/outreach/*`, `/api/landing/deploy`, `/api/runway/revive`, `/api/revenue/log`, `/api/spawn-schedules`, plus unauthenticated `/ws` + sensitive reads. Same architectural gap as the Tony API (B2-class). **Needs an auth decision, not a blind patch** (could lock out the live dashboard).
- **Fixed**: landing-slug traversal + XSS (`cb4e63e`).
- **Queued (B4-class)**: TOCTOU races on CRM / spawn-schedules / site files; raw exception text leaked to clients.

### Frontend full sweep (`auto/mr`, loop `--target .`)
Running over `dashboard-web` lib+app+components. NOTE: the loop is TS-only (no Python) and its ≥2-model consensus gate drops Codex-solo findings — I arbitrate those manually (as with the components round, which yielded fixes #8/#9 + B1).

### Still not reviewed (honest gap) — UPDATED
The `--target .` loop sweeps (run from both repo roots) extended Codex review to the **Python** too. Net result below.

---

## ADDENDUM (round 3 — full `--target .` loop sweeps + cleanup)

**What happened:** three `--apply` loops ran concurrently (two from repo roots + one background) on `auto/mr`. Their Python auto-fixes **all reverted → PLAN** (validation correctly rejected them — no bad auto-edits landed). A separate **Bucket 1 commit `4a8473a`** (test-gated, by another session) then applied the mechanical Python security fixes cleanly.

**Cleanup performed:** reverted 3 orphaned loop-residue files in Tony (`full_e2e_sync_test.py`, `test_backtest_review.py`, `test_funnel_eval.py` — orphaned collateral test edits that broke the suite). Both repos now clean & green: **Tony 1264 / AI Ops 983 pass** (4 pre-existing reds).

### Fixed by Bucket 1 `4a8473a` (AI Ops, +13 tests)
`files._safe_path` (is_relative_to vs startswith) · `vault_memory` role-id allowlist · `landing._path`/`opportunity` slug containment · `data_contract.graded_picks` robustness · `agents/base` unknown-tool handling.

### Remaining Python findings (Codex, queued for sign-off — money-adjacent / architectural)
- **CRITICAL** `dashboard/server.py`: no auth on state-changing endpoints (decision needed — token/mTLS/Tailscale-only).
- **HIGH** `runner/ledger/alpaca_paper.py`: `sync()` has no lock around dedupe `_load(EXECUTED_LOG)` + order submission → overlapping runs can double-submit; `EXECUTED_LOG` plain-write can erase dedupe history on a torn write. *(Live execution path — needs careful review, not a blind patch.)*
- **HIGH** `runner/agents/prompts.py`: vault-writable agent memory injected raw into the system prompt → prompt injection. Needs a trust-boundary/sanitization decision.
- **MED**: `tony_bridge` corrupt-log fail-open · `watcher` broadcasts `{}` on parse failure · outreach status not validated · `market_clock` holiday table only 2026-27.

### Tony Python findings (Codex, analytics/scripts)
- **HIGH** `funnel_eval.build_evaluated_picks` (+ `cli._funnel_eval_signals_from_snapshots`): signals joined by symbol only → repeated picks reuse one snapshot (not point-in-time/as-of). Affects eval accuracy. *(A regression test was drafted by the loop; reverted with the residue — worth implementing properly.)*
- **MED**: `agent_bridge` unlocked RMW race · `backtest_review.win_rate` metric mixing · `seed_vault` future-activity leak · `index_cc_vault` overwrites hand-authored files · several script import-time side effects.

---

## ADDENDUM (round 4 — "fix everything flagged")

After the loop PLANs, I worked through the remaining flagged findings, test-gated, on `auto/mr` (AI Ops) / `auto/mr` (Tony).

### Fixed & committed (round 4)
| Commit | Repo | Severity | Fix |
|---|---|---|---|
| `1d5e803` | AI Ops | HIGH | `alpaca_paper.sync()`: cross-process lock (no double-submit) + atomic executed-log |
| `bffa4ea` | AI Ops | MED | `watcher` partial-read no longer wipes dashboard; `prompts` injection framing; CRM status/notes validation |
| `144f818` | AI Ops | CRITICAL | dashboard **opt-in operator-token auth** on 8 state-changing endpoints |
| `2ad3a5f` | Tony | HIGH | `funnel_eval` as-of signal join (point-in-time); `agent_bridge` atomic writes |

Plus AI Ops `4a8473a` (Bucket 1, prior): `files`/`vault_memory`/`landing`/`opportunity` containment, data-contract + agent-base robustness.

### Verified already-handled (no change needed)
`tony_bridge` corrupt-log (already renames `.corrupt` + atomic write) · `market_clock` holiday table (already 2026-27).

### Remaining punch-list (LOW value / contained — explicitly deferred)
- **AI Ops `dashboard.api_trigger`** (HIGH-ish): spawns an unbounded `run_cycle()` thread per request with no process lock → overlapping cycles. *Mitigated now by the operator-token auth (gates who can trigger); a run_cycle lock is the remaining hardening.*
- **Tony `cli._funnel_eval_signals_from_snapshots`** (MED): still collapses snapshots to one — now that `build_evaluated_picks` supports `signals_history`, wire the CLI to pass it (follow-up).
- **Tony `backtest_review.win_rate`** (MED): counts target/stop hits while P/L drops invalid brackets — metrics can mix denominators.
- **Tony scripts** (LOW): `verify_research_stack` import-time `sys.exit` + missing `sys.path`; `seed_vault` future-activity leak; `index_cc_vault` overwrites hand-authored `_index.md`/`HOME.md`. One-off dev scripts.
- **Operator decisions**: deploy B2 needs `DASHBOARD_ACTION_PIN`; full dashboard auth needs the token set + Tailscale/network choice; B1 control wiring needs manual verification.

### Lesson on the loop
Running 3 `--apply` loops concurrently on one branch tangled git state (one background run's applies were lost in the shuffle). The loop is **TS-aware for apply but its consensus gate + Python validation mismatch means it mostly produces a PLAN for Python** — which is the right outcome (review, don't auto-edit money code). Net value: Codex's findings, arbitrated by hand + the Bucket 1 mechanical fixes.
