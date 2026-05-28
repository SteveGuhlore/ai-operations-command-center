---
task_id: ATLAS-PLAN-20260525-153629
assigned_agent: manager
status: failed
priority: high
pod: management
task_type: planning
created_at: 20260525-153629
---

# Atlas: Spawn Next Revenue Tasks

## Your Job

The task queue is low. Use the `create_task` tool to keep the **two active revenue streams** running. **Spawn 2–4 tasks total — no more.** Quality over quantity.

## ACTIVE Revenue Streams (only spawn for these)

**Stream 1 — Local Web Services (easysimplesites.org)**
- Pitch (outreach_worker) finds no-website businesses, sends pitches → interested replies → Clay (builder) builds the site
- Tiers: Starter $199, Pro $499, Premium $799
- Pitch is SELF-SCHEDULING — only spawn a Pitch task if NONE exists in the queue AND it has been 24+ hours since the last outreach run

**Stream 2 — Stock Research (Tony Stocks)**
- Tony Stocks (market_research_worker) produces a daily trading brief
- Triggered by the trading bot bridge — Atlas should NOT spawn Tony tasks unless explicitly told to

## DISABLED — Do NOT spawn tasks for these agents

The following pods are currently dormant. **NEVER call `create_task` for them**:
- Spark (social_media_worker) — video production OFF
- Muse (content_worker) — content drafting OFF
- Maker (digital_product_worker) — PDF products OFF
- Market (marketing_worker) — listing copy OFF
- Frame (media_worker) — images OFF
- Echo (audio_worker) — audio OFF

If you spawn a task for any disabled agent it will burn API money for nothing.

## What you CAN spawn

| When | Spawn |
|------|-------|
| No Pitch task exists AND last outreach was >24h ago | ONE prospect_research task for outreach_worker |
| Builder has a pending intake and no current task | ONE site_build task for builder |
| Nothing else is appropriate | DO NOTHING — return "queue intentionally empty" and stop |

## Already Done (don't duplicate)

- POD-SOC-001-prompt-pack-promo-script
- POD-SOC-002-affiliate-research
- POD-SOC-003-full-video-chatgpt-titles
- POD-VID-001-script-and-audio
- SAMPLE-001-debug-worker-environment-check
- SAMPLE-002-heavy-worker-implementation-task
- SAMPLE-003-debug-worker-batch-report
- TONY-APPROVAL-PACKAGE-20260519
- TONY-APPROVAL-PACKAGE-20260520
- TONY-APPROVAL-PACKAGE-20260521
- TONY-APPROVAL-PACKAGE-20260522
- TONY-DAILY-BRIEF-20260519
- TONY-DAILY-BRIEF-20260520
- TONY-DAILY-BRIEF-20260521
- TONY-DAILY-BRIEF-20260522
- TONY-EOD-REPORT-20260519
- TONY-EOD-REPORT-20260520
- TONY-EOD-REPORT-20260521
- TONY-EOD-REPORT-20260522
- TONY-TUESDAY-PREP-20260526

## Instructions

If there's nothing legitimate to spawn (Pitch already has a task queued, no builder intakes waiting), call **zero** create_task calls and respond with one sentence explaining why the queue should stay empty. An idle queue is fine — burning money on phantom tasks is not.
