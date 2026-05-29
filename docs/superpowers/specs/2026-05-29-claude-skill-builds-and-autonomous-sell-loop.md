# Spec — Claude-Powered Builds + Autonomous Sell-Loop

**Status:** Draft / design only (no code in this document)
**Date:** 2026-05-29
**Author:** Stephen + Claude
**Related:** [[2026-05-28-prospector-graduation-layer-design]], design-memory loop (`scripts/design_synthesis.py`), runway/doomsday module

---

## 1. Context — where the pipeline stops today

The opportunity pipeline (`runner/main.py:_advance_opportunity_pipeline`) is now:

```
scout → deep-dive → PoC build (Forge) → grade → SHIP: landing build (Clay) → [HUMAN GATE] deploy
```

After the 2026-05-29 reorder, a graduated *promising* PoC is built into a draft
landing page **first**, ahead of more research. Everything up to a built
`workspace/sites/<slug>/index.html` with a `__STRIPE_PAYMENT_LINK__` placeholder is
autonomous. Then four steps are **manual** (the deliberate money-gates):

| Step | Today | Owner |
|------|-------|-------|
| Build the page | Clay (`builder`, `gemini-2.5-flash`) | agent |
| Buy a domain | manual | operator |
| Create the Stripe Payment Link | manual | operator |
| Inject link + publish (`/api/landing/deploy` → Netlify drag-drop) | manual click | operator |
| Record revenue | Stripe / operator only — **agents cannot self-report** | operator |

Two distinct asks motivate this spec:
- **A. Build quality** — route builds through Claude + the skill/design-playbook system so pages are sharp and correct, not slop.
- **B. Full autonomy** — let agents actually *run the sale* on the landing pages, not just draft them.

---

## 2. Part A — Route builds through Claude (skill-powered)

### Problem
Clay (`gemini-2.5-flash`) and Forge (`moonshotai/kimi-k2.5`) build pages/PoCs. The
design-memory loop (`scripts/design_synthesis.py`, the D1 playbook) feeds learned
design rules into the builder prompt, but the *executing model* is a cheap generalist
with no skill framework. Output quality and instruction-adherence are inconsistent.

### Proposal
Add Claude as a selectable **build executor** for `landing_build` (and optionally
`poc_build`), driven by the skill system rather than a single flat prompt.

- **Model routing.** Use the existing per-task-type override hook
  (`config/agents.yaml: task_models:`, resolved in `runner/main.py:TASK_MODEL_OVERRIDES`)
  to map `landing_build → claude-opus-4-8` (or sonnet for cost) without code changes.
  `ANTHROPIC_API_KEY` is already an optional key in `scripts/launch.py`.
- **Skill-powered execution.** Builds invoke a `landing-page` build skill (design
  archetypes, anti-slop rules, accessibility, the hero-image step) instead of one
  monolithic prompt block. The design playbook from `design_synthesis.py` becomes the
  skill's living knowledge, refreshed nightly.
- **Boundary unchanged.** Output contract stays identical: writes
  `workspace/sites/<slug>/index.html`, CTA href = `__STRIPE_PAYMENT_LINK__`, ends with
  `LANDING DRAFTED: <slug>`. So the deploy gate and the dashboard need **zero** change.

### Integration points
- `runner/main.py` model resolution (override only — no logic change).
- `runner/agents/base.py` already speaks an OpenAI-compatible tool-call loop; confirm
  the Anthropic path is wired or add a thin adapter.
- `agents/builder.md` references the build skill; design rules move into the skill.

### Acceptance
A `landing_build` routed to Claude produces a page that (a) honors the placeholder
contract, (b) passes the design-playbook checklist, (c) costs within the per-task cap.

### Part A (preferred) — Gemini + skills, NO new API key

**Claude is optional, not required.** The runner's skill system
(`runner/plugins/loader.py:build_agent_skills_prompt`) injects skill markdown into the
prompt and is **model-agnostic** — skills are plain instruction text, so Gemini consumes
them exactly like Claude. We already pay for Gemini (Vertex/AI-Studio credit), so the
cheapest high-leverage path is:

1. **Wire skills into Clay.** `builder` is currently **absent** from `AGENT_SKILLS`, so
   Clay gets zero skill injection today. Add an entry, e.g.
   `"builder": [("impeccable", "landing-design"), ("everything-gemini-code", "web-ui"), ...]`.
   Install those plugin repos (impeccable / everything-gemini-code / ecc) into the plugin
   cache (`~/.claude/plugins/cache/...`) or extend `_find_skill_file` to their location.
2. **Bump Clay's model** `builder → gemini-2.5-pro` (sharper than `gemini-2.5-flash`,
   still on existing Gemini spend) via the `task_models` override — no code change.
3. **Keep the design playbook** (`design_synthesis.py`) feeding learned rules on top of
   the injected skills.

Reach for Claude (model override → `claude-*`) **only if** Gemini-Pro + skills still
isn't enough; pricing for Claude models is already in `MODEL_PRICING` so cost tracking
works the moment it's enabled. Recommendation: ship the Gemini+skills path first, measure
against the playbook checklist, escalate to Claude per-task only if quality demands it.

---

## 3. Part B — Autonomous sell-loop

Goal: collapse the four manual steps into agent-run steps, **without** weakening the
revenue-truth guard. Each manual step maps to one integration.

### B1. Stripe (payment links + revenue truth)
- **Create Payment Links via the Stripe API** at deploy time instead of pasting one.
  A new tool `create_payment_link(product, price_usd)` returns a `https://buy.stripe.com/...`
  URL that replaces the placeholder.
- **Revenue stays Stripe-sourced.** A Stripe **webhook** (`checkout.session.completed`)
  is the ONLY thing that writes to the revenue ledger — via the existing
  `/api/revenue/log` path, server-side, signed. Agents still **cannot** self-report a
  cent. This preserves the honesty guard that the whole runway/doomsday system depends on.

### B2. Netlify (publish)
- Replace the "drag `workspace/sites/<slug>/` to app.netlify.com/drop" step with the
  **Netlify deploy API / build hook**. `/api/landing/deploy` calls it and stores the
  returned `public_url` in the landing state.

### B3. Registrar (domain)
- Optional, last to automate (real spend + DNS risk). A registrar API
  (Cloudflare Registrar / Namecheap) buys `<product>.<tld>` and points DNS at Netlify.
  Until enabled, fall back to the current `easysimplesites.org/<slug>` path.

### B4. Fulfillment + customer comms
- Stripe webhook on a sale → spawn a `fulfillment` task → the product's agent delivers
  the deliverable and emails the customer (existing `send_email`/SendGrid path).
- Replies route through the existing inbox reader, same as Pitch warm leads.

### Resulting autonomous loop
```
graduate → Claude builds page → create Stripe link → publish to Netlify (+domain)
        → customer buys → Stripe webhook logs REAL revenue → fulfillment + comms
        → revenue extends the runway (doomsday clock)
```

---

## 4. Guardrails (required before any live key is enabled)

1. **Revenue truth is sacrosanct.** Only signed Stripe webhooks write revenue. No agent
   tool can append to the revenue ledger. (Unchanged from today.)
2. **Spend caps.** Domain purchases and any paid API gated by a hard per-day/per-action
   USD cap in `config/budgets.yaml`; exceeding it pauses, never silently spends.
3. **Kill switch.** One dashboard toggle disables all outward money actions (create-link,
   deploy, domain-buy) instantly; falls back to draft-only + human deploy.
4. **Staging first.** Stripe **test mode** + Netlify draft URLs until a full dry-run sale
   completes end-to-end. Promote keys to live only after that passes.
5. **Audit trail.** Every outward action (link created, site deployed, domain bought,
   email sent to a customer) logged with slug, amount, and timestamp.

---

## 5. Rollout phases

| Phase | Scope | Reversible? |
|-------|-------|-------------|
| 0 | Part A: route `landing_build` to Claude + build skill | yes (flip model override back) |
| 1 | Stripe **test-mode** link creation + webhook → ledger (no real charges) | yes |
| 2 | Netlify auto-publish (draft URLs) | yes |
| 3 | Go live: Stripe live keys, public Netlify, kill switch + caps active | gated, kill-switchable |
| 4 | Registrar auto-domain | yes (fall back to ESS path) |
| 5 | Fulfillment + customer-comms loop | yes |

---

## 6. Risks & rollback
- **Agents holding money-spending API keys** is the core real-world risk. Mitigated by
  caps + kill switch + Stripe-webhook-only revenue + staging-first. **This is an explicit
  operator opt-in**, not a default.
- **Bad page goes live autonomously.** Mitigated by the design-playbook checklist gate in
  Part A and Netlify draft URLs in staging.
- **Rollback:** each phase is independently revertible; disabling the kill switch returns
  the system to today's draft-only + human-deploy behavior with no data loss.

---

## 7. Open decisions for the operator
1. Approve agents creating **Stripe Payment Links** programmatically? (Part B1)
2. Approve **auto-domain purchase** with a spend cap, or keep domains manual? (Part B3)
3. Build executor for Part A: **Opus** (max quality) or **Sonnet** (cost)?
4. Which product graduates first into the full autonomous loop as the pilot?
