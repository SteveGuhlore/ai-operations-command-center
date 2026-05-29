# Prospector Graduation Layer — Auto-Build, Sell, and Revenue-Ranked Feedback

**Date:** 2026-05-28
**Status:** Approved design, pending plan
**Author:** spec session (Stephen + Claude)
**Supersedes/revises:** `docs/superpowers/specs/2026-05-28-prospector-phase5-pnl.md` §4.1, §4.3, and §10 (P6 feedback loop pulled into v1). The `log_revenue` tool + revenue ledger are carried over from that spec unchanged.

> This is the **spec**. A separate `writing-plans` session turns it into a task-by-task plan; implementation follows that plan.

---

## 1. Problem statement

The Prospector pipeline can **scout, score, deep-dive, PoC, and grade** AI-agent business ideas, but a "promising" grade is a dead end — `_advance_opportunity_pipeline()` (runner/main.py:318) has no step that acts on it. A proven idea just sits in the ledger as `poc: promising`. Separately, the system tracks **spend only** (`runner/ledger/budget.py`) and has no concept of **income**, so every figure on the Opportunity Board is a projection (`est_rev_mo`) — the system can say "this looks worth ~$900/mo" but never "this earned $312 last month."

This spec closes the loop: a "promising" grade auto-produces a sellable **landing page** with a live Stripe Payment Link (deployed behind one human click), records **real revenue** through a `log_revenue` tool + revenue ledger, feeds that revenue back so **real income outranks the internal composite score**, and bundles graduated products as **upsells to the outreach pod's warm leads**.

**Success in plain language:** A PoC grades "promising." Clay (builder) automatically drafts a product landing page. The operator clicks **Deploy**, pastes the live Stripe Payment Link, and the page goes live under easysimplesites. Sales get logged (manually or, later, reconciled). From then on the dashboard shows that product's real money, the product ranks above unproven ideas by actual revenue, and Pitch offers it as an upsell to warm leads whose business fits.

---

## 2. Scope

**In scope (v1):**
- A **graduation step** in `_advance_opportunity_pipeline()` that fires on `poc == "promising"` with no landing page yet → auto-creates a `landing_build` task for the builder (Clay). Fully autonomous up to the build.
- A **`landing_build` task type** for the builder: a one-page product landing with hero, proven value prop, pricing, and a Stripe Payment Link CTA — saved as a **draft**, not deployed.
- A **one-click deploy gate**: the operator pastes the live Stripe Payment Link, which is validated and injected at deploy time. This is the single human gate and the only moment real-money config enters the system.
- A **`log_revenue` tool + revenue ledger** (`vault/revenue/ledger.md` + `workspace/ledger/revenue.json`), append-only, dedup by `external_id`. Manual entry from day one.
- **Wiring the disabled "💰 Log Revenue" dashboard button** (`dashboard/index.html:755`) + a compact per-pod real-revenue-vs-`est_rev_mo` strip.
- A **revenue → ranking signal**: `rank_score(row)` makes real revenue the primary sort key, composite the tiebreaker. Used in pipeline selection and on the board.
- An **outreach upsell bundle**: deployed products append to `vault/revenue/upsell-catalog.md`; Pitch offers a fitting product to `replied`-status warm leads.

**Out of scope (v1):**
- Automated Netlify deploy (no token; ROADMAP forbids credentials in files). Deploy finalizes the page + surfaces the Netlify-drop step; the operator performs the final drop.
- A Stripe API key of any kind in files. The live Payment Link is a URL pasted at deploy; an optional read-only reconcile feed is deferred (env-only, later).
- Inbound Stripe webhooks, PayPal/affiliate feeds, payouts, refund automation, tax/1099 reporting.
- Auto-deploy. The build is autonomous; going live always requires the human click.

---

## 3. Decisions locked (this session)

1. **Autonomy:** Auto-build the draft landing page on "promising"; **deployment requires a one-click human approval**. (Not fully-auto-deploy; not the full Phase 5 pod-registration gate.)
2. **Stripe:** **Live Payment Link now** — embedded in the page, but injected only at the human deploy click, so no live link sits in a draft or a file beforehand.
3. **Feedback loop:** Implemented in v1 (pulled forward from Phase 5's P6). Real revenue is the **primary** ranking key over composite.
4. **Upsell targeting:** `replied` warm leads **and** only when the product plausibly fits the lead's business type (default; operator may widen to all warm leads).

---

## 4. System overview

```
  scout ─► score ─► deep-dive ─► PoC ─► grade
                                          │ poc: promising
                                          ▼
                              ┌──────────────────────────┐
                              │ GRADUATION STEP (new)     │  autonomous
                              │ pipeline detects promising│
                              │ + no landing → landing_build
                              └────────────┬──────────────┘
                                           ▼
                              ┌──────────────────────────┐
                              │ BUILDER (Clay)            │  autonomous
                              │ writes DRAFT landing page │
                              │ workspace/sites/<slug>/   │
                              │ CTA = __STRIPE_PAYMENT_LINK__
                              └────────────┬──────────────┘
                                           │ draft
                                           ▼
                              ┌──────────────────────────┐
                              │ DEPLOY GATE (1 human click)│ ◄── only human step
                              │ paste live Payment Link    │
                              │ validate → inject → deploy │
                              └───┬───────────────┬────────┘
                                  │ live URL      │ append
                                  ▼               ▼
                    ┌──────────────────┐  ┌──────────────────────┐
                    │ easysimplesites  │  │ upsell-catalog.md     │
                    │ (Netlify drop)   │  │ → outreach warm leads │
                    └──────────────────┘  └──────────────────────┘

  sales ──► log_revenue ──► REVENUE LEDGER (new) ──► P&L strip + rank_score
                            vault/revenue/ledger.md     (real revenue >
                            workspace/ledger/revenue.json composite)
```

**Where each piece lives:**

| Piece | Location | New / edited |
|---|---|---|
| Graduation step | `runner/main.py` `_advance_opportunity_pipeline()` | edited |
| Landing-build behavior | `agents/builder.md` (new task-type section) | edited |
| `landing_build` task type | `runner/tools/task_creator.py` enum + router | edited |
| Draft landing page output | `workspace/sites/<slug>/index.html` | runtime artifact |
| Deploy endpoint + gate | `dashboard/server.py` `/api/landing/deploy`, `/api/landing/pending` | edited |
| Deploy/landing state | `workspace/landings/<slug>.json` (draft/deployed + URL) | new |
| Revenue accessor | `runner/ledger/revenue.py` (mirrors `budget.py`) | new |
| `log_revenue` tool | `runner/tools/revenue_tool.py` | new |
| Revenue ledger | `vault/revenue/ledger.md` + `vault/revenue/_moc.md` | new |
| Machine mirror | `workspace/ledger/revenue.json` | new |
| Log-revenue endpoint | `dashboard/server.py` `/api/revenue/log` | edited |
| Dashboard button + P&L strip | `dashboard/index.html` | edited |
| `rank_score` | `runner/tools/opportunity.py` | edited |
| Upsell catalog | `vault/revenue/upsell-catalog.md` | new |
| Upsell behavior | `agents/outreach_worker.md` (new section) | edited |

`runner/ledger/budget.py` is **not touched** — revenue is a parallel module so a revenue bug can never corrupt the spend caps protecting active pods.

---

## 5. Components

### 5.1 Graduation step (pipeline)
In `_advance_opportunity_pipeline()`, after the PoC-build step and before the fresh-scout fallback, add: select rows where `poc == "promising"` and no landing exists yet (`workspace/landings/<slug>.json` absent). Pick the top by `rank_score` (§5.6). Create a `landing_build` task (`assigned_agent="builder"`, `pod="opportunity_pod"`). Idempotent: the presence of the landing-state file prevents re-queueing.

### 5.2 Builder landing page (`landing_build`)
New section in `builder.md`. Clay reads `vault/opportunities/<slug>.md` (value prop, who-pays, pricing hypothesis) and writes `workspace/sites/<slug>/index.html`: hero with the proven value, a short proof/demo section, pricing, and a primary CTA `<a href="__STRIPE_PAYMENT_LINK__" ...>`. Same design standards as client sites (mobile-first, embedded CSS, footer credit). Output summary ends with `LANDING DRAFTED: <slug>`. Writes `workspace/landings/<slug>.json` with `status: draft`. **Never deploys; never invents a Payment Link URL** — the placeholder stays literal until the deploy gate.

### 5.3 Deploy gate
- `GET /api/landing/pending` → drafts awaiting deploy (for a dashboard card).
- `POST /api/landing/deploy {slug, payment_link_url}`:
  1. Validate `payment_link_url` matches `^https://(buy\.stripe\.com|[a-z0-9.-]+\.stripe\.com)/...` — refuse anything else (prevents a dead/placeholder or non-Stripe button going live).
  2. Replace `__STRIPE_PAYMENT_LINK__` in `index.html` with the validated URL.
  3. Set `workspace/landings/<slug>.json` `status: deployed`, store the URL + `deployed_at` + the easysimplesites public path.
  4. Append the product to `vault/revenue/upsell-catalog.md`.
  5. Return the Netlify-drop instruction + public URL.
- This is the **only** human gate and the only point a live Payment Link enters the system.

### 5.4 `log_revenue` tool + revenue ledger (carried from Phase 5 spec)
- `runner/ledger/revenue.py`: `record_revenue(pod, amount_usd, source, external_id, kind="sale", note="")`, `get_pod_revenue(pod)`, `get_revenue_total()`. Mirror of `budget.py`; never merged with spend on disk.
- `vault/revenue/ledger.md` row: `| date | pod | amount_usd | kind | source | external_id | note |`. `kind` ∈ {sale, refund, adjustment, manual}. Append-only; corrections are reversing rows.
- `workspace/ledger/revenue.json`: `{ by_pod, total_usd, seen_external_ids }`. Dedup by `external_id` (blank for manual/adjustment).
- `runner/tools/revenue_tool.py` exposes `log_revenue` (agent tool + callable from the dashboard endpoint).

### 5.5 Dashboard button + P&L strip
Wire `dashboard/index.html:755` "💰 Log Revenue" from disabled → opens a small inline form (pod dropdown, amount, source, optional note) → `POST /api/revenue/log` → `log_revenue`. Add a compact per-pod strip: `revenue_to_date` vs `est_rev_mo`, net of `get_pod_spend(pod)`, with the honesty-rule framing (estimate vs. reality side by side). Reuses existing state/WS plumbing.

### 5.6 Revenue → ranking signal
Add `rank_score(row)` to `opportunity.py`, returning a sort tuple `(has_revenue, revenue_usd, composite)` where `revenue_usd = get_pod_revenue(row["pod"])` when the row is graduated (has a real `pod`), else `0`. Higher tuple sorts first, so **any earning opportunity outranks any projection-only one**, earners order by revenue, the rest by composite. Replace the `max(..., key=lambda r: r["composite"])` selections in `_advance_opportunity_pipeline()` and the board ordering with `rank_score`. `est_rev_mo` (estimate) is never overwritten — real revenue is a separate signal.

### 5.7 Outreach upsell bundle
- `vault/revenue/upsell-catalog.md`: one row per deployed product — `| product | one_liner | landing_url | fits_business_types |`. The deploy step appends; `fits_business_types` is derived from the opportunity's who-pays (operator-editable).
- New section in `outreach_worker.md`: at the start of a run, read the upsell catalog. When processing a **warm lead** (CRM status `replied`), if a catalog product's `fits_business_types` plausibly matches the lead's business type, include a one-line upsell in the follow-up. Default targeting is `replied` + type-fit; the operator can widen to all warm leads by clearing `fits_business_types`. Cold/`new` leads never receive upsells.

---

## 6. Risks (ranked)

1. **A draft deploys with a dead/placeholder/non-Stripe button.** → Deploy validates the URL against the Stripe host pattern and refuses otherwise; the placeholder is never a valid link.
2. **Real money mishandled.** → No Stripe API key in files; the live Payment Link is operator-created and injected only at the human deploy click; nothing is publicly reachable until then; payouts/refunds out of scope.
3. **Upsell spams cold leads / off-topic businesses.** → Gated to `replied` status **and** business-type fit; cold/`new` leads excluded.
4. **Phantom/double-counted revenue inflates rank.** → Append-only ledger, dedup by `external_id`, reversing-row corrections; `est_rev_mo` and real revenue are separate columns.
5. **Runaway graduated work burns budget.** → Landing builds run under `opportunity_pod`'s existing hard cap via the untouched `budget.py` path; `local_outreach_pod` and Tony caps are independent.
6. **Revenue accounting bug corrupts spend caps.** → Revenue is a parallel module; the two ledgers are never merged on disk.

---

## 7. Open questions (deferred to plan stage)

1. **Upsell targeting breadth** — default is `replied` + type-fit (§3.4). Confirm, or widen to all warm leads.
2. **Read-only Stripe reconcile feed** — manual `log_revenue` only in v1; an env-only read-only poll feed can be a fast-follow. Confirm v1 is manual-only.
3. **Landing page pricing** — pull tiers from the opportunity's pricing hypothesis, or a single price the operator sets at deploy? Recommend: builder drafts from the hypothesis, operator can edit before deploy.

---

## 8. Success criteria

v1 is **done** when:
1. A `poc: promising` row with no landing auto-produces a `landing_build` task; the builder writes a draft `index.html` with a literal placeholder CTA and a `draft` landing-state file; re-running the cycle does not re-queue it.
2. `POST /api/landing/deploy` with a valid Stripe URL injects it, flips state to `deployed`, appends to the upsell catalog, and returns the public URL + drop step; an invalid/non-Stripe URL is refused with no file change.
3. `log_revenue` appends to `vault/revenue/ledger.md`, updates `revenue.json`, dedups by `external_id`, and a reversing row reduces the total; the spend ledger is provably untouched.
4. The dashboard button logs revenue through the endpoint; the P&L strip shows per-pod revenue vs `est_rev_mo` vs net.
5. `rank_score` sorts any earning opportunity above any projection-only one; the pipeline selects and the board orders by it.
6. A deployed product with matching `fits_business_types` is offered to a `replied` warm lead; a cold/`new` lead and a non-matching business are not.
7. Isolation holds: `budget.py`, `local_outreach_pod`, and Tony are unchanged; no credentials in files; deploy and live money are behind the one human click.
8. `pytest -q` green (ledger math, dedup, reversing rows, deploy URL validation, idempotent graduation, `rank_score` ordering, isolation check).
