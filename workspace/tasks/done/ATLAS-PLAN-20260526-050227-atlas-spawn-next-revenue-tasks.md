---
task_id: ATLAS-PLAN-20260526-050227
assigned_agent: manager
status: done
priority: high
pod: management
task_type: planning
created_at: 20260526-050227
---

# Atlas: Spawn Next Revenue Tasks

## Your Job

The task queue is low. Your number-one priority is keeping **Easy Simple Sites** (the local-outreach revenue pod) running continuously. You MUST call `create_task` at least once unless there is already a `prospect_research` task queued for outreach_worker.

## ACTIVE Revenue Streams (only spawn for these)

**Stream 1 — Easy Simple Sites (local Massachusetts web design)**
- Pitch (outreach_worker) finds no-website MA businesses, sends pitches → interested replies → Clay (builder) builds the site
- Brand: Easy Simple Sites — easysimplesites.org — signed "Stephen"
- Tiers: Starter $299, Pro $499, Premium $799
- **DEFAULT BEHAVIOR**: If no `prospect_research` task is queued for outreach_worker, spawn ONE now. Do not wait 24 hours — Pitch is allowed to run multiple times per day. The only reason to skip is "a prospect_research task is already queued".

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
| **No outreach_worker task in the queue** | ONE `prospect_research` task for outreach_worker (this is the default — do this almost every cycle) |
| Builder has a pending intake and no current task | ONE `site_build` task for builder |

## Pitch task body template (use this exactly when spawning)

```
title: "Pitch: Daily Outreach"
task_type: prospect_research
assigned_agent: outreach_worker
pod: local_outreach_pod
priority: high
body: |
  Run the standard outreach workflow for Easy Simple Sites (easysimplesites.org).

  GEO ROTATION — work through these in order, picking cities not used in the last 3 runs.
  Check your memory for recently covered cities and skip them.

  MASSACHUSETTS (primary — exhaust these first):
  Boston, Worcester, Springfield, Cambridge, Lowell, Brockton, Quincy, Lynn,
  New Bedford, Fall River, Newton, Somerville, Framingham, Haverhill, Waltham,
  Salem, Medford, Everett, Lawrence, Malden, Revere, Weymouth, Peabody, Taunton,
  Attleboro, Fitchburg, Leominster, Chicopee, Holyoke, Pittsfield, Westfield,
  Agawam, Northampton, Amherst, Gloucester, Plymouth, Barnstable, Methuen,
  Chelsea, Amesbury, Andover, Beverly, Billerica, Burlington, Chelmsford,
  Dracut, Marlborough, Milford, Natick, Norwood, Randolph, Stoughton, Tewksbury,
  Watertown, Woburn, Dedham, Lexington, Needham, Milton, Canton, Mansfield

  STALENESS RULE — if you find fewer than 5 new unique prospects across 2+ MA city
  searches in this run, MA inventory is getting thin. Add one city from a neighboring
  state to your search for this run and note it in memory.

  NEIGHBORING STATES (use when MA is getting stale):
  Rhode Island: Providence, Cranston, Warwick, Pawtucket, Woonsocket, East Providence
  Connecticut: Hartford, New Haven, Bridgeport, Stamford, Waterbury, New Britain, Norwich
  New Hampshire: Manchester, Nashua, Concord, Dover, Portsmouth, Rochester
  Maine: Portland, Lewiston, Bangor, Auburn, Augusta
  Vermont: Burlington, Rutland, South Burlington, Barre

  CATEGORIES — rotate broadly, pick ones not used in the last 2 runs:
  hair salons, barbershops, nail salons, beauty salons, eyelash studios, spas,
  auto repair shops, car washes, auto detailing,
  restaurants, food trucks, bakeries, cafes, catering services,
  plumbers, electricians, HVAC contractors, roofers, painters, handymen, general contractors,
  cleaning services, carpet cleaners, pest control,
  landscaping services, lawn care, tree services,
  dog groomers, pet shops, boarding kennels,
  daycares, after-school programs, tutoring centers,
  martial arts studios, yoga studios, fitness studios, personal trainers,
  tattoo shops, massage therapists,
  florists, photographers, videographers,
  dry cleaners, laundromats, tailors,
  moving companies, junk removal,
  accountants, notaries, insurance agents

  CONTACT LOOKUP — after find_prospects, for each no-website business call web_research
  (action=search, query="[Business Name] [City] MA contact email OR instagram") ONCE per
  prospect. If email found → send_email + status email_sent. If IG handle found →
  send_instagram_dm + status dm_queued. If nothing found → status call_queued (phone only).
  Limit to 1 web_research call per prospect — do not retry.

  Sign all pitches as Stephen, easysimplesites.org. Never reference any other brand.
```

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

The only acceptable reason to call `create_task` zero times is: a `prospect_research` task for outreach_worker is ALREADY in the queue. Otherwise, you MUST spawn one using the template above. Idle queues kill the revenue pipeline.


## Agent Output

I have assessed the task queue and found it to be empty. In accordance with my primary directive to maintain revenue pipeline activity, I will now spawn one high-priority `prospect_research` task for the `outreach_worker` to keep the Easy Simple Sites stream active.

| Task ID | Agent | Title |
|---|---|---|
| `AUTO-20260526-051750-pitch-daily-outreach` | outreach_worker | Pitch: Daily Outreach |
