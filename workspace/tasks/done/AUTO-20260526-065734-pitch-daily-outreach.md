---
task_id: AUTO-20260526-065734-pitch-daily-outreach
assigned_agent: outreach_worker
status: done
priority: high
pod: local_outreach_pod
task_type: prospect_research
created_at: 20260526-065734
---

# Pitch: Daily Outreach

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


## Agent Output

Run completed via tool calls: read_inbox, find_prospects, web_research, send_instagram_dm, file_editor, flag_issue. Check CRM for new entries.
