# Staging Workflow — the only road to production

Production (`/opt/command-center`, `cc-runner`, :8765, `master`) runs 24/7 and is **never**
edited, restarted with uncommitted code, or deployed to directly. Every change travels:

**dev branch → staging soak → promote gate → fast-forward master → prod restart (after close)**

The scanner repo (`/opt/trading-bot` → twin `/opt/trading-bot-staging`, services
`tradingbot-api-staging` :8002 + `tradingbot-watch-staging`, flag `TONY_LLM_OFFLINE`) follows
this identical workflow with its own copies of the scripts.

---

## The staging twin — what it is

A git **worktree** of this repo at `/opt/command-center-staging` (shares the object store; the
dev branch is checked out there while prod next door stays on `master`). Own venv, own `.env`,
own state, dashboard on **:8766**, service `cc-runner-staging`. Functionally identical to prod
except hermetically sealed:

| Seal | Mechanism |
|---|---|
| $0 LLM spend | `CC_LLM_OFFLINE=1` (canned verdicts, 0 tokens) + ALL model keys blank |
| No shared trading book | its OWN throwaway Alpaca paper account (never prod's keys) |
| No outside contact | Telegram / SendGrid / Instagram hard-off in `.env` |
| No prod-grading pollution | verdict/report paths repointed inside the staging checkout |
| On-demand only | started by hand for a soak, stopped after promotion, never boot-enabled |

## Bootstrap (ONCE per machine — already done on the VM 2026-06-12)

```bash
sudo mkdir -p /opt/command-center-staging && sudo chown $USER:$USER /opt/command-center-staging
git -C /opt/command-center fetch origin <branch>
git -C /opt/command-center worktree add /opt/command-center-staging <branch>
bash /opt/command-center-staging/scripts/setup_staging.sh <branch>   # run STAGING'S copy
# then: throwaway paper keys into the .env, verify (below), install unit, START (never enable)
```

## The dev loop (every piece of work)

1. **Develop** — a Claude session works on a fresh dev branch and pushes. Sessions never run
   VM commands against the prod checkout; staging commands below are run by the operator.
2. **Ship to staging:**
   ```bash
   cd /opt/command-center-staging
   git fetch origin && git checkout <branch> && git pull --ff-only
   sudo systemctl restart cc-runner-staging      # or start, if stopped
   ```
3. **Iterate** — watch :8766 + `workspace/logs/staging-runner.log`. Bug? The session pushes a
   fix; `git pull --ff-only && sudo systemctl restart cc-runner-staging`. Repeat freely.
4. **Soak** — one evening of live market data minimum (CLAUDE.md rule).
5. **Promote** — `bash /opt/command-center-staging/scripts/promote_staging.sh`. Gates: full
   pytest + readiness sweep + liveness, against the exact soaked commit. On green it PRINTS the
   ff-only merge + prod restart commands — run them by hand, after 4 PM ET.
6. **Stop staging** — `sudo systemctl stop cc-runner-staging`. Twins stay off between soaks.

## Pre-start safety gate (every time, both twins)

```bash
grep -n  '^CC_LLM_OFFLINE='                          /opt/command-center-staging/.env  # =1
grep -nE '^(OPENROUTER_API_KEY|GOOGLE_AI_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|VERTEX_PROJECT)=' \
                                                     /opt/command-center-staging/.env  # all blank
grep -nE '^ALPACA_(API_KEY|SECRET_KEY)='             /opt/command-center-staging/.env  # staging keys ONLY
```
If the Alpaca lines show a prod key, or `CC_LLM_OFFLINE` is missing: **do not start.** A twin
started on prod keys trades the same paper book prod is actively trading.

## Post-soak contract (what "passed" means)

- `workspace/ledger/daily-spend.json` → `total_usd: 0.0` **exactly**, every soak day
- verdicts / paper trades / EOD report all produced (functional coverage, not an idle box)
- staging service stayed `active` through day rollovers (no crash loops)

## Rules of thumb

- One branch in staging at a time; a new branch waits for the current soak to finish.
- Multi-repo changes (verdict schema, bridge format): run BOTH twins, soak together, promote both.
- Full-fidelity soak (real LLM keys, only when the change IS the LLM path): set
  `CC_LLM_OFFLINE=0` + real keys for that ONE soak, then revert. Rare, deliberate, never default.
- Emergency direct prod fix (should be never): immediately re-point staging at master afterward
  so histories re-converge, or the next ff-only promote will refuse.
- Operator-only sudo: install/start/stop of staging units; sessions provide commands, never run them.
