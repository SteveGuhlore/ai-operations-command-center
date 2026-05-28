# Prospector Phase 5 — Graduation & Real P&L

**Date:** 2026-05-28
**Status:** Draft spec, pending plan
**Author:** spec session (Stephen + Claude)
**Extends:** `docs/superpowers/specs/2026-05-27-prospector-design.md` §10 and `docs/superpowers/plans/2026-05-27-prospector.md` Phase 5 note (lines 1818–1825)

> This is the **spec**. A separate `writing-plans` session turns it into a task-by-task plan; implementation follows that. Per the plan doc (line 1820), Phase 5 "gets its own spec → plan cycle when P1–P4 have proven out" — P1–P4 are now landed on `feat/prospector-phases-1-4`, so this spec opens that cycle.

---

## 1. Problem statement

Phases 1–4 gave the system the ability to **discover, score, prototype, and grade** AI-agent business ideas. The Opportunity Board surfaces a ranked shortlist with a hard honesty rule: every dollar figure is a *projection* (`est_rev_mo`), never booked income (design §8, "Honesty rule"). The system can tell the operator *"this idea looks worth ~$900/mo"* — it cannot yet tell them *"this idea made $312 last month and cost $47 to run, net +$265."*

That gap exists because the ledger is **half a ledger**. `runner/ledger/budget.py` tracks **spend only** — `record_spend(role_id, cost_usd, pod)` debits `workspace/ledger/daily-spend.json`; there is no credit side. So the system knows its costs to six decimal places and knows nothing about its income.

Phase 5 closes the loop. It introduces the lifecycle transition where a *proven* opportunity stops being a hypothesis and becomes a **real revenue pod** that earns measured money: an operator-approved **graduation** step, a **revenue ledger** (the missing credit side), an **approval-gated payment-provider feed** that populates it, and a **P&L dashboard panel** that shows spend vs. revenue vs. net per pod.

**Current state it transitions out of:** fully-autonomous, FYI-only, projection-only. No real external accounts, no real income, no human gate inside the Prospector loop (design §2, "Human gate: None on P1–P4").

**Success in plain language:** The operator clicks **Graduate** on a promising idea. The system stands up a real pod, connects a payment provider behind an approval gate, and from then on the dashboard shows that pod's *actual* money — what it earned, what it cost, and whether it is net-positive — next to the original estimate, so the operator can see whether Prospector's projections were any good. No money moves, no account is touched, and no key is used without an explicit human approval first.

---

## 2. Scope

**In scope (Phase 5 v1):**
- A **graduation action** that converts one `status: graded / promising` opportunity row into a registered real revenue pod.
- A **revenue ledger** (`vault/revenue/ledger.md`) — append-only credit side, mirroring the spend ledger's shape and discipline.
- A `log_revenue` agent tool / CLI for **manual and reconciled** revenue entry.
- **One** payment provider: **Stripe**, **read-only / poll-based** reconciliation (rationale in §4.3). No inbound webhook server in v1.
- A **P&L panel** on the existing dashboard: per-pod spend, revenue, net, vs. the original estimate.
- **Pod registration** of the graduated pod into the same config + budget machinery Phases 1–4 already use.
- An **approval gate** (the `NEEDS_HUMAN` pattern) on graduation *and* on first live-key connection.

**Out of scope (explicitly):**
- Moving money *out* (payouts, supplier payments, ad spend on real platforms).
- Auto-graduation. A human always clicks the button. There is no composite-score threshold that graduates anything by itself.
- Changing the Prospector P1–P4 loop's autonomy. Scouting/speccing/PoC/grading stay exactly as they are.

**Deferred to P6+:**
- Inbound Stripe **webhooks** (real-time, signed) — v1 polls; webhooks need a public HTTPS endpoint + signature verification, a larger attack surface (§7).
- **PayPal** and **affiliate-network** feeds (each is its own auth model + reconciliation shape).
- Multi-pod graduation in one action, automated tax/1099 reporting, refund automation, payout/disbursement.
- A graduated pod spawning *its own* sub-opportunities (recursion).

---

## 3. System overview

Phase 5 adds the **right half** of a money loop the system has only ever had the left half of.

```
        P1–P4 (exists)                    │  P5 (this spec)
                                          │
  scout ─► score ─► spec ─► PoC ─► grade  │
   (vault/opportunities/ledger.md)        │
                    │                     │
              promising row               │
                    │                     │
                    ▼                     │
          ┌───────────────────┐  approve  ┌──────────────────────┐
          │  GRADUATION GATE   │──gate────►│  graduated pod entry │
          │  NEEDS_HUMAN       │  (deny/   │  config/revenue-pods │
          │  manifest          │  timeout) │  + budgets.yaml cap  │
          └───────────────────┘           └──────────┬───────────┘
                    │ approved                        │
                    ▼                                 ▼
        ┌───────────────────────┐         ┌────────────────────────┐
        │ payment provider feed │ poll    │  SPEND side (exists)    │
        │ Stripe (read-only key)│────────►│ workspace/ledger/       │
        │  approval-gated        │         │   daily-spend.json      │
        └───────────┬───────────┘         └────────────────────────┘
                    │ log_revenue                       │
                    ▼                                    │
        ┌───────────────────────┐                       │
        │ REVENUE LEDGER (new)  │                       │
        │ vault/revenue/        │                       │
        │   ledger.md           │                       │
        └───────────┬───────────┘                       │
                    └──────────────┬────────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  P&L PANEL (dashboard)        │
                    │  spend vs revenue vs net /pod │
                    │  vs. original est_rev_mo      │
                    └──────────────────────────────┘
```

**Where each piece lives in the repo:**

| Piece | Location | New / edited |
|---|---|---|
| Graduation tool + CLI | `runner/tools/graduation.py` (new) + `scripts/graduate.py` (new) | new |
| Graduation manifests | `workspace/graduations/{pending,approved,denied}/` (new) | new |
| Revenue ledger | `vault/revenue/ledger.md` + `vault/revenue/_moc.md` (new) | new |
| Revenue accessor | `runner/ledger/revenue.py` (new) — mirrors `budget.py` | new |
| `log_revenue` tool | `runner/tools/revenue_tool.py` (new) | new |
| Provider feed | `runner/integrations/stripe_feed.py` (new) | new |
| P&L panel | `dashboard/server.py` (`/api/pnl`) + `dashboard/index.html` panel | edited |
| Pod registration | `config/revenue-pods.yaml` (promote example→real), `config/budgets.yaml`, `runner/tools/task_creator.py` pod enum | edited |
| Approval endpoint | `dashboard/server.py` (`/api/graduation/decide`) | edited |

The spend side (`runner/ledger/budget.py`) is **not touched** — revenue is a parallel module, so a bug in revenue accounting can never corrupt the budget caps that protect the active pods.

---

## 4. Components

### 4.1 Graduation command

**Purpose:** Convert one proven opportunity into a registered real revenue pod, behind a human gate.

**Surface — both:**
- **Agent tool** `request_graduation(slug)` — Prospector (or the operator via the dashboard) can *propose* a graduation. This **never** graduates; it only writes a pending manifest and flips the ledger row to `status: graduation_pending`.
- **CLI** `python scripts/graduate.py --approve <slug>` / `--deny <slug>` — the actual approval, run by the operator (or the dashboard's approve button calling the same code path).

**Inputs:** `slug` (must exist in `vault/opportunities/ledger.md` with `status` in {`graded`, `promising`}). Optional `--pod-id`, `--display-name`, `--monetization-model`, `--daily-cap-usd` overrides; otherwise derived from the opportunity page.

**Outputs / side effects of an *approved* graduation (in order, idempotent):**
1. Write `config/revenue-pods.yaml` entry for the new pod (matching the `revenue-pods.example.yaml` schema: `pod_id`, `display_name`, `monetization_model`, `assigned_agents`, `required_tools`, `allowed_task_types`, `forbidden_task_types`, `approval_required_for`).
2. Add a `per_pod_limits.<pod_id>` block to `config/budgets.yaml` (default `daily_spend_limit_usd` = the opportunity's `est_run_cost` × a safety multiple, floored at $2).
3. Add `<pod_id>` to the `task_creator.py` pod enum.
4. Create `vault/revenue/<pod_id>.md` (per-pod revenue page) and a `graduation_manifest` (§5).
5. Flip the opportunity ledger row: `status: graduated`, `pod: <pod_id>` (the `pod` column already exists — design §4 forward-compatible fields).
6. Move the manifest `pending/ → approved/`.

**Idempotency:** Keyed on `pod_id`. Re-running approve on an already-graduated slug is a no-op that logs and returns the existing pod_id. Config edits are upsert-by-key, never blind-append, so a double-run cannot create duplicate pod blocks.

**Failure modes:**
- Slug not found / wrong status → refuse, no writes.
- `pod_id` collides with an existing pod → refuse (don't clobber an active pod's budget).
- Config write fails mid-sequence → the manifest stays in `pending/` and records `partial: true` with the last completed step, so re-approve resumes rather than half-registers. No money capability is enabled until **all** steps complete.

### 4.2 Revenue ledger

**Purpose:** The credit side. Source of truth for "what came in," structurally separate from spend.

**Location:** `vault/revenue/ledger.md` (markdown table, Obsidian-visible, mirrors `vault/opportunities/ledger.md` and Tony's signal-ledger). A machine mirror `workspace/ledger/revenue.json` is the fast read for the dashboard (mirrors `daily-spend.json`).

**Append-only.** A correction is a new reversing row (negative `amount_usd`, `kind: adjustment`), never an in-place edit — same discipline as accounting and the same reason the spend ledger is monotonic (`budget.py` only ever adds).

**Who writes:**
- The **Stripe feed** (§4.3) via `log_revenue` for reconciled charges.
- The **operator/script** via `log_revenue` for manual entries (cash, Venmo, anything off-Stripe).
- **Never** a Prospector agent autonomously, and **never** the spend path.

**Relation to budget tracking:** Revenue lives in `runner/ledger/revenue.py`, a deliberate mirror of `budget.py` (`record_revenue(pod, amount_usd, source, external_id)`, `get_pod_revenue(pod)`, `get_revenue_total()`). Net P&L is computed at read time as `get_pod_revenue(pod) − get_pod_spend(pod)` — the two ledgers are never merged on disk. `external_id` (Stripe charge id) is the dedup key so polling the same charge twice cannot double-count.

### 4.3 Payment-provider integration

**Which provider, v1:** **Stripe**, **read-only, poll-based.** Rationale:
- Stripe fits the first realistic graduation target (Easy-Simple-Sites-style one-off site sales, $199/$499/$799 — design references `local_outreach_pod` as the pod template).
- A **restricted, read-only** API key (`charges:read`, `balance_transactions:read`) can list income with **zero ability to move money** — the cleanest possible match to the project's "no real external actions" guardrail (ROADMAP "Stop conditions").
- **Polling** instead of webhooks means **no public endpoint, no inbound signature surface, no always-on listener** — the runner already wakes on a cycle (`run_cycle`), so a once-per-cycle reconcile call fits the existing daemon with no new attack surface. Webhooks are deferred to P6 (§2).

**Auth model:** Key read from an environment variable (`STRIPE_RESTRICTED_KEY`), **never from a file** (ROADMAP stop condition: "Stop if any step requires credentials in files"). A missing key disables the feed and the panel shows "provider not connected" — it never blocks the runner.

**Reconciliation flow (per cycle, only if the pod is graduated and the key is present):**
1. List Stripe balance transactions since the last `external_id` cursor (stored in `workspace/ledger/revenue-cursor.json`).
2. For each new charge: `record_revenue(pod, amount_usd, source="stripe", external_id=<txn id>)`.
3. Advance the cursor. Dedup is by `external_id`, so a re-run is safe.

**Sandbox vs. live keys:** v1 ships against **Stripe test mode** keys first (test charges reconcile end-to-end with no real money). Switching to a **live** restricted key is itself an **approval-gated action** — a second `NEEDS_HUMAN` manifest (`live_key_connect`) separate from graduation, so "stand up the pod" and "connect real money" are two distinct human decisions.

**Refunds:** A Stripe refund appears as a negative balance transaction and reconciles like any other row (negative `amount_usd`, `kind: refund`). No special path; the append-only model handles it for free.

**Graceful degradation:** Provider unreachable / rate-limited / key revoked → log a warning, leave the cursor unchanged, panel shows last-known totals with a stale-data badge. The runner and all other pods are unaffected (the feed is wrapped like every other integration: failure is logged, never raised into the cycle).

### 4.4 P&L dashboard panel

**Purpose:** Show, per graduated pod, **real** money: spend, revenue, net, and how that compares to Prospector's original `est_rev_mo` projection (the honesty-rule payoff — estimate vs. reality, side by side).

**Slots in:** a new read-only panel below the Opportunity Board, same dark-neon aesthetic, same `.panel` card + glowing-bar styling (design §8). It reuses the existing WebSocket/state plumbing — no new transport.

**REST endpoint:** `GET /api/pnl` (new, alongside `/api/opportunities`, `/api/spawn-gate`). Shape:

```json
{
  "pods": [
    {
      "pod_id": "ai-review-reply-agent",
      "display_name": "AI Review Reply Agent",
      "graduated_on": "2026-06-02",
      "est_rev_mo": 900.0,
      "revenue_mtd": 312.40,
      "spend_mtd": 47.10,
      "net_mtd": 265.30,
      "provider": "stripe",
      "provider_status": "connected",
      "last_reconciled": "2026-06-09T14:02:00",
      "anomaly": null
    }
  ],
  "stale": false
}
```

**Refresh cadence:** pushed on the existing WebSocket whenever the runner reconciles (per cycle); the panel also re-fetches `/api/pnl` on a timer as a fallback (matching how the board already polls).

**Anomaly highlighting:** the panel flags, in amber/red:
- **net negative** for a graduated pod (it's costing more than it earns) → red border.
- **revenue far below estimate** (e.g. < 25% of `est_rev_mo` after 30 days) → amber "underperforming vs. projection" — this is the feedback signal that tells the operator Prospector's scoring over-promised.
- **stale provider data** (last reconcile > 24h) → grey badge.

### 4.5 Pod registry update

**Purpose:** Make the graduated pod a first-class pod the existing machinery already understands, so spend-tracking, spawn-gating, and the dashboard need **no special-casing**.

- **Config:** promote `config/revenue-pods.example.yaml` into a real `config/revenue-pods.yaml` (the example schema is already exactly right — §4.1 writes one entry into it).
- **Budget model:** the **same per-pod cap system** — a `per_pod_limits.<pod_id>` block in `budgets.yaml`, enforced by the existing `is_pod_budget_exceeded` / `get_pod_cap` path (`budget.py`). No new budget mechanism; a graduated pod is capped exactly like `opportunity_pod` and `local_outreach_pod`. (`per_poc_limit_usd` is omitted for graduated pods — that's a Prospector-only concept.)
- **Spawn-gate:** if the graduated pod runs recurring tasks, add a `by_pair` / `by_agent` entry to `config/spawn-schedules.yaml` (ROADMAP "Per-Agent Spawn Schedules" — no code change, the gate re-reads the file). It then appears in the spawn-gate panel automatically via `gate_snapshot()`.

---

## 5. Data model

**Revenue ledger row** (`vault/revenue/ledger.md`):

```
| date | pod | amount_usd | kind | source | external_id | note |
|------|-----|-----------|------|--------|-------------|------|
| 2026-06-09 | ai-review-reply-agent | 49.00 | sale | stripe | ch_3Pabc... | Pro plan |
| 2026-06-11 | ai-review-reply-agent | -49.00 | refund | stripe | re_3Pxyz... | customer refund |
```
- `kind` ∈ {`sale`, `refund`, `adjustment`, `manual`}.
- `external_id` unique per provider row; blank for `manual`/`adjustment`.

**Machine mirror** (`workspace/ledger/revenue.json`, mirrors `daily-spend.json`):
```json
{ "by_pod": { "ai-review-reply-agent": 263.40 },
  "total_usd": 263.40,
  "seen_external_ids": ["ch_3Pabc", "re_3Pxyz"] }
```

**Graduation manifest** (`workspace/graduations/pending/<slug>.yaml`):
```yaml
slug: ai-review-reply-agent
pod_id: ai-review-reply-agent
display_name: AI Review Reply Agent
monetization_model: subscription_software_revenue
proposed_daily_cap_usd: 3.00
est_rev_mo: 900.0
requested_by: prospector
requested_at: 2026-06-01T09:14:00
status: pending            # pending | approved | denied | expired
decided_by: null
decided_at: null
partial: false             # set true if approval aborted mid-sequence
completed_steps: []        # for resume-on-retry
```

**Payment record:** the reconciled Stripe transaction is *not* stored as its own file — it becomes a revenue-ledger row + an entry in `seen_external_ids`. The cursor lives in `workspace/ledger/revenue-cursor.json`:
```json
{ "stripe": { "last_txn_id": "txn_3Pabc", "last_reconciled": "2026-06-09T14:02:00" } }
```

**Pod registration:** see `revenue-pods.example.yaml` schema (§4.1) — graduated pods use it verbatim.

---

## 6. Approval gate design

The `NEEDS_HUMAN` pattern from earlier phases (ROADMAP isolation guarantee: "No live spend… without an explicit operator `NEEDS_HUMAN` gate"), realized as a **manifest-in-a-folder** state machine that mirrors the task lifecycle (`todo/done/failed`):

```
workspace/graduations/pending/  → human decides →  approved/  (pod registered)
                                                 →  denied/    (row reverts)
                                                 →  (timeout)  stays in pending/
```

**How a human approves:**
- **Dashboard:** an Approve / Deny button on a pending-graduation card → `POST /api/graduation/decide {slug, decision}` (same shape as the existing `/api/outreach/update-status` and `/api/trigger` endpoints). The endpoint calls the same `scripts/graduate.py` code path.
- **CLI fallback:** `python scripts/graduate.py --approve <slug>`.

**State location:** the manifest file *is* the state (single source of truth, git-visible, survives restarts). The opportunity ledger row mirrors it (`graduation_pending` → `graduated` / back to `graded`).

**If denied:** the ledger row reverts to `status: graded`, the manifest moves to `denied/` with `decided_by`/`decided_at`. No pod is created, no config touched. The idea stays on the board and can be re-proposed later.

**If no human responds within N hours (default 72h):** the manifest **stays pending forever** — it does **not** auto-approve. A `request_graduation` re-proposal just refreshes the timestamp. Money capability defaults to *off*; only an explicit human click turns it on. (We deliberately reject a timeout-auto-approve: an unattended approval that connects a payment provider is exactly the failure this gate exists to prevent.) After N hours the board badges it "awaiting approval (3d)" so it doesn't silently rot.

A **second, independent gate** guards live keys: graduation against Stripe **test mode** needs only the graduation approval; flipping to a **live** restricted key requires a separate `live_key_connect` manifest approval (§4.3).

---

## 7. Risks (ranked)

1. **Real money loss via the wrong key.** A *writable* Stripe key could move money. **Mitigation:** v1 uses a **restricted read-only** key (`charges:read` only); the spec forbids any write-scope key; live keys are a separate gate; the key lives in env, never in a file. This is the single most important constraint.
2. **Key theft / leakage.** A leaked key exposes income data (read-only) — bad, not catastrophic. **Mitigation:** env-only, restricted scope, never logged, never committed; `.gitignore` covers `workspace/ledger/*cursor*` and any `.env`.
3. **Runaway graduated pod.** A new pod burns budget. **Mitigation:** it inherits the same hard `per_pod_limits` cap as every pod via the untouched `budget.py` path; it cannot starve `local_outreach_pod` / `market_research_pod` (those caps are independent).
4. **Double-counted / phantom revenue → false P&L.** Over-counting income could make a losing pod look profitable. **Mitigation:** append-only ledger keyed on `external_id`; corrections are reversing rows; the estimate (`est_rev_mo`) and actuals live in separate columns (design §4 — "a real measured number never overwrites an estimate").
5. **Regulatory: sales tax / 1099 / provider TOS.** Booking real revenue has tax and reporting implications; Stripe TOS governs automated access. **Mitigation:** v1 is **read/reconcile only** — it records what already happened, it doesn't transact, so it adds no new regulatory action beyond what the operator already does by selling. Tax/1099 automation is explicitly out of scope (§2); the P&L panel is an *internal* view, not a tax document. Flag this as an open question (§8) — the operator should confirm with their own accounting.
6. **Vendor lock-in (Stripe).** Building only for Stripe. **Mitigation:** `record_revenue(pod, amount, source, external_id)` is provider-agnostic; `stripe_feed.py` is one adapter behind it — PayPal/affiliate are future adapters writing the same ledger (§2 deferred).
7. **Provider downtime breaks the dashboard.** **Mitigation:** the feed is failure-isolated (§4.3) — it degrades to last-known totals with a stale badge; the runner and other pods never see the error.

---

## 8. Open questions / decisions deferred to plan stage

Each is framed as a choice with a recommendation; the operator weighs in before the plan is written.

1. **First provider: Stripe vs. PayPal vs. affiliate.**
   *Recommendation:* **Stripe, read-only poll.** It matches the realistic first graduation (site/subscription sales), and a restricted read-only key is the lowest-risk way to touch real money. PayPal/affiliate add auth+reconciliation shapes with no extra v1 value. *Decide:* confirm Stripe, or name a different first provider if the real income is already flowing through PayPal/an affiliate network.

2. **Webhooks now or poll-only?**
   *Recommendation:* **Poll-only in v1.** Webhooks need a public HTTPS endpoint + signature verification — real attack surface for marginal freshness gain on a once-per-cycle dashboard. Defer to P6. *Decide:* accept poll-only, or accept the added surface for near-real-time.

3. **Where does the graduated pod's daily cap come from?**
   *Recommendation:* **derive from the opportunity's `est_run_cost` × safety multiple, floored at $2,** operator-overridable at approve time. *Decide:* derive-with-floor, or always prompt for an explicit cap per graduation.

4. **Approval timeout behavior.**
   *Recommendation:* **never auto-approve; pending forever + a board "awaiting approval" badge.** *Decide:* confirm, or set a different N-hour reminder cadence (the choice is *which reminder*, not *whether to auto-approve* — auto-approve on money is off the table).

5. **Manual revenue entry in v1?**
   *Recommendation:* **yes — ship `log_revenue` for manual/off-Stripe income from day one.** It's the MVP credit side and the fallback when a provider isn't connected; Stripe reconciliation is an automated *source* feeding the same tool. *Decide:* manual + Stripe, or Stripe-only.

6. **Tax/accounting posture.**
   *Recommendation:* **treat the P&L panel as an internal operating view, not a tax record;** keep tax/1099 out of scope and let the operator's existing accounting own it. *Decide:* confirm internal-only, or flag tax-export as an early P6 item.

7. **Test mode first?**
   *Recommendation:* **yes — reconcile against Stripe test mode end-to-end before any live key,** with the live key behind its own gate. *Decide:* confirm the two-stage (test → gated live) rollout.

---

## 9. Success criteria

Phase 5 v1 is **done** when:

1. **Graduation works end-to-end:** `request_graduation(slug)` writes a pending manifest and flips the row to `graduation_pending`; an operator Approve (dashboard or CLI) registers a real pod in `revenue-pods.yaml` + `budgets.yaml` + the task_creator enum, flips the row to `graduated`, and is **idempotent** (re-approve is a no-op). Deny reverts cleanly.
2. **Revenue ledger is real:** `log_revenue` appends to `vault/revenue/ledger.md`; `get_pod_revenue(pod)` returns the correct sum; a reversing row correctly reduces the total; the spend ledger is provably untouched.
3. **Stripe test-mode reconcile:** a test charge appears as a revenue row exactly once (re-running the cycle does not double-count); a test refund appears as a negative row; a missing key disables the feed without breaking the runner.
4. **P&L panel shows real numbers:** `/api/pnl` returns per-pod spend/revenue/net + `est_rev_mo`; the panel renders them, badges net-negative red and underperforming-vs-estimate amber, and shows a stale badge when reconcile is > 24h old.
5. **No money can move:** a code review confirms no write-scope payment capability exists anywhere; live-key connect is gated separately; no credentials live in files.
6. **Isolation holds:** `local_outreach_pod` and `market_research_pod` behavior, budgets, and the Atlas/Pitch loop are provably unchanged; the Prospector P1–P4 loop is unchanged.
7. **Tests pass:** unit (ledger math, dedup, idempotent graduation, cap derivation), a mocked Stripe reconcile, and an isolation check, all green in `pytest -q`.

---

## 10. Migration / backwards-compatibility

Phase 5 was **designed-for** in Phases 1–4, so the migration surface is small:

- **Opportunity ledger schema — no change.** It already carries `status` (supporting `graduated`) and a `pod` column (design §4 forward-compatible fields; plan line 1822). Phase 5 *uses* those columns; it doesn't add any. `est_rev_mo` stays the estimate column; real numbers go in the **separate** revenue ledger, never overwriting it.
- **Dashboard board — no change.** The board reads the opportunity ledger generically (plan line 1823: "a future P&L panel adds a new data source… without changing the board"). The P&L panel is a **new** panel + a **new** `/api/pnl` endpoint reading a **new** source (`vault/revenue/`). Existing `/api/opportunities` is untouched.
- **`budget.py` — no change.** Revenue is a parallel `revenue.py` module. Per-pod caps work unchanged; graduated pods just add new `per_pod_limits` entries.
- **Scoring rubric — no change.** The six dimensions and 75/75 auto-promotion thresholds stay. (Phase 5 *creates* the estimate-vs-actual feedback signal the P4 learning loop could later consume — but wiring that into scoring is a P6 enhancement, not part of v1.)
- **Dashboard tabs — additive.** One new panel below the Opportunity Board; nothing removed or re-laid-out.
- **`revenue-pods.example.yaml` → `revenue-pods.yaml`.** The example becomes the live file; the schema is unchanged, so no field migration. If code currently reads the `.example.` path, point it at the real file (verify with a grep before the plan).

Nothing built in Phases 1–4 needs to be rewritten. Phase 5 is purely **additive** plus three small **edits** (P&L panel, pod-config promotion, task_creator enum), each behind the approval gate and isolated from the active revenue pipelines.
