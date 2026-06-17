# Multi-review backlog (AI Ops Command Center)

From the 2026-06-17 multi-model audit (Claude Opus 4.8 + Codex gpt-5.4 high + Gemini 2.5-pro).
Full report: `reviews/2026-06-17-000945-full-multirepo/MASTER-REPORT.md`. **Fixed items are in git
history on the merge.** This file tracks what's intentionally left for later.

## Remaining engineering work
- [ ] **`dashboard/server.py` `api_trigger`** (HIGH-ish): spawns an unbounded `run_cycle()` thread per
      request with no process-wide lock → overlapping cycles. *Partly mitigated* by the new
      operator-token auth (gates who can trigger). Fix: a `run_cycle` mutex (skip if one is running),
      same pattern as `alpaca_paper._acquire_sync_lock`.
- [ ] **`dashboard/server.py` spawn-schedules / CRM / site writes** (MED): TOCTOU read-modify-write on
      shared files. Use a lock + atomic replace (atomic-write helper already used in budget/runway).
- [ ] **`runner/ledger/*` lost-update locks** (MED): budget/runway/audit are now atomic-write
      (corruption-safe) but still lack a cross-process lock for true lost-update protection.

## Documented design tradeoffs — decide whether to revisit (NOT bugs)
- `cluster_risk` unknown ticker → `'other'` (not capped): deliberate (avoids false-blocking
  uncorrelated buys). Real fix = expand ticker map / dynamic sector lookup.
- `runway` revive-on-missing-file: deliberate (a bug can't brick the pod; grace deadline bounds it).
- `get_offhours_cap()` infinite default + `decision_audit` fail-open: both documented intentional.

## Operator action items (before VM deploy)
- [ ] **Set `DASHBOARD_OPERATOR_TOKEN`** on the VM + have the dashboard send `X-Operator-Token`,
      else the state-changing endpoints stay open by design. Keep the server Tailscale/localhost-bound.
- [ ] Decide the dashboard auth model (token vs mTLS vs network-only).
