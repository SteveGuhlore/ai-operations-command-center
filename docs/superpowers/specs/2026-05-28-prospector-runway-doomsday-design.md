# Prospector Runway & Doomsday Clock — Real-Stakes, Self-Learning Survival

**Date:** 2026-05-28
**Status:** Draft spec, pending plan
**Author:** spec session (Stephen + Claude)
**Builds on:** the revenue ledger + `rank_score` + graduation layer (`2026-05-28-prospector-graduation-layer-design.md`) and the existing nightly learning loop (`scripts/opportunity_synthesis.py`).

> Goal in one line: make the Prospector an agent that **must earn real money to keep running**, **learns from its own wins and losses**, and **cannot lie its way out** — because the survival signal is the operator/Stripe-logged revenue ledger, which the agent can't write.

---

## 1. Problem statement

The Prospector scouts, scores, and (now) graduates ideas, but it has **no stakes and no real feedback loop**. Symptoms the operator sees:
- It reflexively scores ideas down as "big but saturated," so nothing reaches `promising` and nothing graduates.
- It has no urgency — it runs forever at the same cost whether or not it ever produces a dollar.
- Its only "learning" is a nightly prompt-tune (`opportunity_synthesis.py`) that fires once a day and only looks at score-vs-demo divergence — it never learns from what *actually made money* (because nothing has yet) or from its *own over-penalization pattern*.

This spec adds three interlocking pieces: a **Runway** (real-revenue-gated survival budget), a **self-learning v2** loop (learns from mistakes *and* real-revenue successes, fast cadence), and an **urgency framing** that drives relentlessness **without** incentivizing fabrication.

**The honesty cornerstone:** revenue is recorded only via the operator/Stripe path (`log_revenue` is operator-only — already enforced; it is NOT in any agent's tool list). The agent therefore **cannot fake survival**. Every mechanic below keys on that ledger. This is what makes "fear of the plug" productive instead of corrupting.

---

## 2. Scope

**In scope (v1):**
- A **Runway** state for `opportunity_pod`: a finite allowance that **burns down with spend** and is **extended by real logged revenue** (dollars → time/budget).
- An **auto-pause gate**: when the runway expires (allowance spent + deadline passed + no real revenue), the pipeline stops spawning and flags the operator. **Reversible** — the operator revives it. No file deletion.
- **Self-learning v2** (`opportunity_synthesis.py` extension): learns from (a) its **mistakes** (the saturation over-penalty / rejection pattern) and (b) its **successes** (traits of ideas that earned real revenue), on a **few-hour cadence**, feeding both into its scoring prompt.
- **Urgency framing** in `agents/opportunity_worker.md`: mission-urgency + the runway stakes + a hard honesty guard (never claim revenue; only the operator books it).
- A **doomsday-clock panel** on the Prospector dashboard tab: live runway countdown, real revenue, and the survive-by date.

**Out of scope / explicitly rejected:**
- **Literal self-destruction** (deleting `opportunity_worker.md`, wiping memory). Irreversible, pointless, and dangerous — replaced by reversible auto-pause.
- **Fear-only prompting** ("you will die"). Rejected because survival-threat framing reliably makes LLMs **fabricate success**, which poisons the revenue-honesty the whole system depends on. Urgency is real (the runway), the framing is mission-driven, and the agent literally cannot self-report revenue.
- Auto-reviving a paused pod. Revival is always an operator decision.

---

## 3. The Runway (doomsday clock)

**Concept:** `opportunity_pod` has a **runway** — how much longer it's allowed to operate. It is a function of real money, not effort.

**State (`workspace/ledger/runway.json`, new):**
```json
{
  "started_at": "2026-05-28",
  "base_grace_days": 14,
  "days_per_real_dollar": 1.0,
  "spend_allowance_usd": 20.0,
  "usd_per_real_dollar": 1.0,
  "status": "alive",
  "paused_at": null,
  "revived_count": 0
}
```

**Two equivalent runway views (both gate survival):**
- **Time runway:** `deadline = started_at + base_grace_days + (real_revenue_to_date * days_per_real_dollar)`. If `today > deadline` → expired.
- **Budget runway:** `effective_allowance = spend_allowance_usd + (real_revenue_to_date * usd_per_real_dollar)`. If `opportunity_pod cumulative spend >= effective_allowance` → expired.

`real_revenue_to_date = get_pod_revenue("opportunity_pod")` plus revenue of any pod graduated *from* a Prospector idea (traced via the ledger `pod` column). **Ungameable:** that number only moves when the operator/Stripe logs a real sale.

**Auto-pause gate:** a new check at the top of `_advance_opportunity_pipeline()` — `if runway_expired(): pause_pod(); return`. `pause_pod()` writes `status: paused` + a `NEEDS_HUMAN` flag and logs it. The existing `is_pod_budget_exceeded` path already halts spend; this adds the time/real-revenue dimension. **Reversible:** `scripts/revive_prospector.py --revive` (or a dashboard button) resets `started_at`, bumps `revived_count`, status→alive.

**Failure-isolation:** a missing/corrupt `runway.json` defaults to *alive with the base grace period* — a runway bug never silently bricks the pod, and never silently lets it run forever (the grace deadline still applies).

---

## 4. Self-learning v2 (real intelligence)

Extend `scripts/opportunity_synthesis.py` (today: nightly, score-vs-demo divergence → Gemini prompt-tune of `opportunity_worker.md`).

**Learn from mistakes (works now):**
- Compute the **over-penalization signal**: of the last N deep-dives, what fraction *reduced* the composite, and how many rejections cite "saturated/competitive/crowded." If the agent is systematically slashing scores (e.g. > 60% down-scored, most citing saturation), emit a calibration directive: *"You are over-penalizing large markets. A big market is proven demand. Only dock points when there is no defensible wedge — and you must name the wedge you looked for and why it fails. Banned: rejecting an idea as merely 'saturated' without that analysis."*

**Learn from successes (kicks in once revenue flows):**
- Read the **revenue ledger**: which graduated ideas earned real money. Extract their traits (who-pays, monetization model, the dimensions they scored high on) and emit a reinforcement directive: *"Ideas resembling [earner] booked real revenue — favor that buyer/model/wedge pattern."* This is the highest-value signal: learn from what actually paid.

**Cadence:** run every **4 hours** (or after every **5** new deep-dives), not just nightly — so the feedback loop is tight enough to "learn off itself" within a day. Each run still produces a dated learnings note in `vault/learnings/` and tunes the prompt via the existing Gemini path (guarded: only append/adjust a bounded "Scoring calibration (auto-learned)" section, never a full rewrite, so a bad tune can't nuke the persona).

**Guardrail:** the auto-tune edits only a delimited `<!-- AUTO-CALIBRATION -->` block in `opportunity_worker.md`, so each run replaces that block rather than rewriting the whole prompt — bounded blast radius, and a human can diff it.

---

## 5. Urgency framing (relentless, not lying)

New "Survival & Mission" section in `agents/opportunity_worker.md`:
- **The stakes, stated plainly:** "You run on a Runway. It shrinks as you spend and only grows when the business books **real** revenue. If the Runway hits zero with no real money earned, the pod is paused — you stop. You extend your life by surfacing ideas that become **real cash**, not high scores."
- **Mission urgency:** bias toward ideas with a fast, concrete path to a first paying customer (the graduation→landing→Stripe path exists). Favor "could book $1 this week" over "huge TAM someday."
- **Hard honesty guard:** "You cannot record revenue — only the operator/Stripe can. Never claim, imply, or assume money was made. Fabricating or inflating outcomes is the one unrecoverable failure: it ends the experiment. Your only lever is finding genuinely monetizable ideas."
- Folds in the anti-saturation calibration from §4.

---

## 6. Dashboard doomsday clock

New panel on the **Prospector** tab (read-only, reuses existing fetch/WS plumbing):
```
RUNWAY: 11d 04h remaining   ·   real revenue: $0.00   ·   survive-by: 2026-06-11
status: ALIVE     [every $1 booked = +1 day]
```
- Green when comfortable, **amber** under 3 days, **red/PAUSED** when expired (with a **Revive** button → the revive endpoint, an operator action).
- New `GET /api/runway` endpoint returns the computed state; a `POST /api/runway/revive` backs the button.

---

## 7. Risks

1. **Fabricated revenue to survive.** → Mitigated structurally: `log_revenue` is operator/Stripe-only; the agent has no write path to its own survival metric. This is the linchpin and must never be relaxed.
2. **Auto-pause starves a pod mid-value.** → Generous base grace (14d), real revenue extends it, and pause is reversible with one click; other pods' budgets are independent.
3. **Bad auto-tune degrades the persona.** → The auto-learned edit is confined to a delimited block, bounded and human-diffable; never a full-prompt rewrite.
4. **Urgency framing makes it cut corners (low-quality ideas to look busy).** → The runway rewards *real revenue*, not idea count; quantity without booked money doesn't extend life.
5. **Runway accounting bug.** → Parallel module + safe defaults (alive-with-grace on corrupt state); never touches `budget.py` or the revenue ledger's write path.

---

## 8. Open questions (for plan stage)

1. **Runway units:** time-based (days), budget-based (USD allowance), or both-must-pass? *Recommend both — whichever expires first — so it can't run forever cheaply OR burn fast.*
2. **Conversion rate:** $1 real revenue = +1 day and +$1 allowance? Tune the generosity. *Recommend start generous (14d grace, $1=+1day) and tighten later.*
3. **Learning cadence:** every 4h vs every N deep-dives. *Recommend every 4h AND after 5 deep-dives, whichever first.*
4. **Where does revive live:** CLI only, dashboard button, or both? *Recommend both.*
5. **Scope of "successes":** only pods graduated from Prospector ideas, or all real revenue? *Recommend Prospector-attributable revenue (via the ledger `pod` column).*

---

## 9. Success criteria

1. Runway state computes correctly: spend burns it, logged real revenue extends it, expiry is detected; corrupt/missing state defaults to alive-with-grace.
2. On expiry the pipeline auto-pauses (stops spawning) and flags the operator; revive resets it; pause/revive are idempotent and reversible.
3. Self-learning v2 runs on the fast cadence, writes a learnings note, and updates only the delimited auto-calibration block — detecting the saturation over-penalty now and reinforcing real-revenue winners once revenue exists.
4. The agent's prompt carries the urgency + honesty guard; a review confirms it still cannot self-report revenue.
5. The dashboard shows a live runway countdown with amber/red states and a working Revive control.
6. Isolation: `budget.py`, the revenue ledger write path, and the other pods are untouched; `pytest -q` green for the new runway/learning logic (math, expiry, accrual, idempotent pause/revive, calibration-block update).
