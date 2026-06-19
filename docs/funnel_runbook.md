# Trades Acquisition Funnel — Runbook

How to deploy and operate the `local_outreach_pod` client-acquisition funnel (find → score → enrich →
personalize → hand off). Code is on branch `claude/eager-curie-tfw2zc`.

## Components
- **Funnel (Python, in this repo):** `runner/tools/places.py` (discovery + review fields),
  `runner/tools/lead_score.py` (offer router + hook), `runner/tools/apify.py` (`enrich_contacts`),
  `runner/tools/cold_export.py` (cold hand-off), `agents/outreach_worker.md` (playbook).
- **Actor A (JS+Crawlee):** `actors/site-contact-extractor/` — deployed to *your* Apify account; called
  by `enrich_contacts`.
- **Gate:** `runner/main.py` `OUTREACH_PAUSED` (keep `True` until the validation gate passes).
- **Spend cap:** `config/budgets.yaml` → `per_pod_limits.local_outreach_pod` ($3/day default).

## 1. Deploy Actor A (headless-friendly; never on the production checkout)
```bash
npm i -g apify-cli                                    # prereq (+ node) on a box that can reach api.apify.com
git -C /opt/command-center fetch origin claude/eager-curie-tfw2zc
git -C /opt/command-center worktree add /tmp/cc-actor origin/claude/eager-curie-tfw2zc
cd /tmp/cc-actor/actors/site-contact-extractor
apify login -t <PERSONAL_API_TOKEN>                  # Apify Console → Settings → API & Integrations (no browser)
apify push                                            # actor id => <your-username>~site-contact-extractor
git -C /opt/command-center worktree remove /tmp/cc-actor
```
If the VM can't reach Apify, run the same steps from your laptop. `apify login -t` avoids the blocked
browser flow.

## 2. CC environment (`.env`)
```
# Lead enrichment (Actor A)
APIFY_TOKEN=<token>
APIFY_CONTACT_ACTOR=<your-username>~site-contact-extractor
# Discovery (already set)
GOOGLE_MAPS_API_KEY=<key>
# Cold sending — only when automating (Phase 1); leave unset for Phase-0 CSV mode
COLD_EMAIL_PROVIDER=instantly            # or smartlead
COLD_EMAIL_API_URL=<provider add-leads endpoint>
COLD_EMAIL_API_KEY=<key>
COLD_EMAIL_CAMPAIGN_ID=<campaign>
COLD_PHYSICAL_ADDRESS="<CAN-SPAM mailing address>"   # required for API export
COLD_BOOKING_URL=<calendly/cal.com link>
# Gate to send warm/reply email (SendGrid) — cold NEVER uses this
OUTREACH_AUTOMATION=false
```

## 3. Phase-0 validation (no cold infra; minimal spend)
- Keep `OUTREACH_PAUSED=True` and `OUTREACH_AUTOMATION=false`.
- Run one `outreach_compose` cycle (or the pod once) → it finds → `score_and_hook` → `enrich_contacts`
  (needs Actor A deployed for real emails) → composes → `export_cold_leads` writes a CSV to
  `vault/outreach/cold-export/`.
- Send that batch from your own inbox/phone to validate messaging. Log outcomes in the CRM
  (`vault/outreach/crm.md`) via the pod (`cold_export` → `booked`/`replied`).

## 4. Go-live gate (before flipping the switch)
`scripts/outreach_synthesis.py` surfaces sent/reply/booked in the AUTO-CALIBRATION block. Thresholds:
- **≥50 handed-off**, **≥5% reply**, **≥3 booked** → set `OUTREACH_PAUSED=False` (Phase 1).
- **<2% reply on ≥50** → stop; revise copy/ICP before spending more.

## 5. Cold provider (Phase 1 automation)
Set the `COLD_EMAIL_*` vars + `COLD_PHYSICAL_ADDRESS`, warm a **separate** sending domain
(SPF/DKIM/DMARC, slow ramp, low daily volume). `export_cold_leads` then pushes to the provider API;
otherwise it always falls back to CSV. Email-only — **no cold SMS** (TCPA).

## Verify
```bash
# Actor logic (offline): cd actors/site-contact-extractor && node test/extract.test.mjs
# Actor live:  apify call <username>~site-contact-extractor  (input {"urls":["https://<a trade site>"]})
# Consumer:    PYTHONPATH=. python -c "from runner.tools.apify import enrich_site_contacts as e; print(e(['https://example.com']))"
# Funnel wiring: PYTHONPATH=. python -c "import runner.main as m; print('enrich_contacts' in [t['name'] for t in m.ROLE_TOOLS['outreach_worker']])"
```

## Safety
- Cold goes through `export_cold_leads` only; `send_email` (SendGrid) is warm/reply-only.
- `local_outreach_pod` is spend-capped; `enrich_contacts` refuses to run over the cap.
- No fabricated reviews (`score_and_hook` returns no hook below a review floor); review *automation* is
  compliant generation only — never gate/filter reviews.
