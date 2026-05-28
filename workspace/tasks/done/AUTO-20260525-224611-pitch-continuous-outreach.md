---
task_id: AUTO-20260525-224611-pitch-continuous-outreach
assigned_agent: outreach_worker
status: done
priority: high
pod: local_outreach_pod
task_type: prospect_research
created_at: 20260525-224611
---

# Pitch: Continuous Outreach

Run your autonomous lead generation workflow for Easy Simple Sites (easysimplesites.org).
Your goal: find local businesses with NO website and pitch them a professionally built site.

GEO: Start with Massachusetts cities not recently covered. If MA searches yield fewer than
5 new prospects, expand to a neighboring state city (RI, CT, NH, ME, or VT). Check your
memory to avoid repeating recently searched cities.

CATEGORIES: Rotate broadly — hair salons, barbershops, nail salons, auto repair, restaurants,
food trucks, bakeries, plumbers, electricians, HVAC, roofers, painters, cleaners, landscapers,
dog groomers, daycares, tutors, martial arts, yoga studios, tattoo shops, florists,
photographers, dry cleaners, moving companies, accountants, notaries.

SPEED RULE — CRITICAL: Do NOT use web_research to look up contact info. It hits CAPTCHA
every time and wastes the entire run. Use ONLY what find_prospects returns (phone number
is enough — status: call_queued). Skip web_research for email lookup entirely.

Sign as Stephen, easysimplesites.org. Full autonomy — use whatever sources work best.


## Agent Output

Run completed via tool calls: read_inbox, file_editor, find_prospects. Check CRM for new entries.
