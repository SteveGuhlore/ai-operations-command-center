# Development Workflow — staging soak before main

Production is a 24/7 systemd service (`cc-runner`, dashboard `:8765`) at
`/opt/command-center`, trading a $1M Alpaca paper account. Broken code on
`master` = a broken live service. So:

**Rule: no code lands on `master` without an evening soak in staging.**

## The loop

1. **All work on a dev branch.** Never commit straight to `master`.
2. **Evening soak.** Check the branch out in staging (`/opt/command-center-staging`,
   dashboard `:8766`) and let it run while real market data flows through the
   mirrored bridge. Watch the dashboard, logs, and task queue.
3. **Promote after close.** Run `scripts/promote_staging.sh` — full pytest +
   readiness sweep + liveness gate. It prints (never runs) the exact
   ff-only merge + deploy commands.

## One-time setup (on the VM)

```bash
bash /opt/command-center/scripts/setup_staging.sh <dev-branch> --mirror-bridge
# then the printed sudo commands:
sudo cp /tmp/cc-runner-staging.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cc-runner-staging.service
```

Strongly recommended before the first real soak: create a **second free Alpaca
paper account** and fill the `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` placeholders
at the bottom of `/opt/command-center-staging/.env` (see warning below), then
`sudo systemctl restart cc-runner-staging`.

## Per-evening loop

```bash
cd /opt/command-center-staging
git fetch origin
git checkout <your-dev-branch>          # or: git pull --ff-only on the same branch
sudo systemctl restart cc-runner-staging   # module cache: restart after ANY code change
# watch:  http://127.0.0.1:8766
#         tail -f workspace/logs/staging-runner.log
#         journalctl -u cc-runner-staging -f

# after market close:
bash scripts/promote_staging.sh         # gates, then prints the deploy commands
```

If requirements.txt changed on the branch, re-run `setup_staging.sh <branch>`
(idempotent) before restarting.

## Known sharing hazards — and how the kit isolates each

| Hazard | Why it's shared | Isolation |
|---|---|---|
| **Verdicts / bot reports dir** | `TONY_VERDICTS_FILE`, `TONY_OUTCOMES_FILE`, `TONY_RECORD_FILE`, `TONY_INSIGHTS_FILE`, `TONY_IDEAS_FILE`, `TONY_REPORTS_DIR` all *default* to `<repo-parent>/TradingBotAgentProject/reports` — the live bot's dir, identical from both checkouts. Staging writing verdicts there would feed the production bot. | `setup_staging.sh` force-overrides all six to `workspace/trading-reports/` inside the staging checkout. **Never remove these overrides.** |
| **Bot bridge dir** | The trading bot drops handoffs only into `/opt/command-center/bridge/tony-stocks/`. | Staging's `TONY_BRIDGE_DIR` points at its own `bridge/tony-stocks/`. `--mirror-bridge` installs a 1-minute cron that copies **new files only** from production's bridge + reports dirs (never deletes/overwrites/writes back), so staging sees live handoffs read-only. |
| **Alpaca paper account** | `.env` is copied from production, so staging inherits the same paper keys and **will place orders on the same $1M account** — duplicate orders, polluted equity curve. | Loud warning at setup; placeholders in `.env` for a second free paper account (recommended). Live trading is hard-disabled in staging (`TONY_ACCOUNT_MODE=paper`, live keys blanked). |
| **Dashboard port** | Production owns `:8765`; `scripts/launch.py` hardcodes it and refuses to start when it's busy. | Staging runs its own generated launcher on `:8766` (`CC_PORT`). |
| **Outbound sends** | Same Telegram/SendGrid/Instagram creds in the copied `.env` — a soak could DM real leads or post publicly. | Hard-off in staging: `TONY_NOTIFY/TONY_TELEGRAM_CHAT/TONY_PUBLIC=off`, tokens blanked, `OUTREACH_AUTOMATION=false`. |
| **workspace/ + vault/** | — not shared: all other state paths resolve relative to the checkout, so staging gets fresh copies automatically (verified per env var in `setup_staging.sh` comments). | Nothing to do. |

## Staging spends $0 — offline by default

Staging is a **functional tester only, never a second producer**. Prod LLM spend is
~$50/day and a rehearsal with no audience must not double it. Two independent
guarantees, both installed by `setup_staging.sh`:

1. **`CC_LLM_OFFLINE=1`** — `runner/agents/base.py` skips client construction and
   `_completion_with_backoff` returns canned, real-shaped completions
   (`runner/agents/offline.py`, 0 tokens → `record_spend` books exactly $0). The
   canned market-research completion emits `write_tony_verdict` tool calls **with
   plausible target/stop**, so the real pipeline still runs end to end: verdicts →
   `plan_orders` buys (they survive the never-open-naked guard) → paper brackets →
   reconcile → EOD report. Functional coverage, zero spend.
2. **All model keys blanked** in the staging `.env` (`OPENROUTER_API_KEY`,
   `GOOGLE_AI_API_KEY`, `VERTEX_PROJECT`, `GOOGLE_CLOUD_PROJECT`,
   `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) — even if the flag is ever missed, there
   is no credential to bill against.

After a soak, verify: `workspace/ledger/daily-spend.json` in the staging checkout
must read **total_usd: 0.0 exactly**, while verdicts/trades/EOD all exist.

**Full-fidelity opt-in (rare):** only when the change under test *is* the
LLM/reasoning path — set `CC_LLM_OFFLINE=0` and paste real keys for that one soak,
accept the few dollars, revert to offline after. Never the default. Offline staging
validates the **code**, not Tony's reasoning quality — that isn't staging's job.

**The two knobs, side by side** (don't mix them up):

| Twin | Flag | Where it lives |
|---|---|---|
| CC staging | `CC_LLM_OFFLINE=1` | `/opt/command-center-staging/.env` |
| Scanner staging | `TONY_LLM_OFFLINE=1` | `/opt/trading-bot-staging/.env` |

**On-demand rule:** start the twins for a soak, stop them after promotion
(`sudo systemctl stop cc-runner-staging` / `tradingbot-watch-staging`). Never 24/7.

## The scanner staging twin (the other half of the tandem)

The bot repo now has the matching kit: `scripts/setup_staging.sh` there builds
`/opt/trading-bot-staging`, with every exchange path (bridge briefs, outcomes,
insights, verdict/record reads) repointed at **this** staging checkout
(`/opt/command-center-staging`). See the bot repo's `docs/DEVELOPMENT.md`.

Two rules that involve this side:

- **Mirror-bridge either/or:** while the scanner twin is running, the
  `--mirror-bridge` cron must be OFF — otherwise production scan output and the
  twin's output both land in staging's bridge and the soak grades garbage.
- **Schema-change trigger:** staging-CC's verdict write-back is severed from the
  live bot on purpose, so a CC change to the format of the five exchange files
  (`tony_stocks_verdicts/outcomes/record/ideas.json`, `agent_insights.json`) or
  to the bridge/tier report format is **invisible to CC staging alone**. Any such
  change → spin up the scanner twin and soak the full round trip before promoting.

Other notes:

- Staging is a **git worktree** of the production clone (shared object store,
  trivial branch switching). If you ever delete the staging dir, clean up with
  `git -C /opt/command-center worktree remove /opt/command-center-staging`
  (or `... worktree prune`).
- `BOT_API_BASE` (`:8001`) stays shared on purpose — read-only GETs against the
  bot's API for the head-to-head equity curve.
- `setup_staging.sh` never writes into `/opt/command-center`'s working tree and
  never restarts `cc-runner`; `promote_staging.sh` never pushes or restarts
  anything — production only changes when you run the printed commands yourself.
