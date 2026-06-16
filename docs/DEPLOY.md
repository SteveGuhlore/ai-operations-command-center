# Deploy runbook (VM)

The command-center runs on the VM at `/opt/command-center` (systemd `cc-runner`, deploys from
`master`); the bot runs at `/opt/trading-bot` (deploys from `main`). The canonical script
`/opt/trading-bot/scripts/deploy/update_vm.sh` deploys **both** (git pull → deps → dashboard
rebuild → restart services), so a single run brings the whole stack current.

> **Policy vs mechanics.** This is the *how*. The *when/whether* gate is `CLAUDE.md` →
> Branch Discipline: dev branch → staging soak (`scripts/setup_staging.sh`) → promote via
> `scripts/promote_staging.sh` (tests + readiness) → deploy, outside market hours. Don't deploy red.

---

## Two ways to deploy

### A. On-demand GitHub Action — preferred (no SSH)
A self-hosted runner **on the VM** runs the deploy and reports back through GitHub, so a deploy can
be triggered and verified entirely from GitHub (including by Claude via the GitHub MCP).

1. GitHub → repo → **Actions → “Deploy to VM” → Run workflow** → `mode: deploy`.
2. The runner runs `update_vm.sh` (serialized with `flock`) then a **verify** step: `cc-runner` +
   `tradingbot-api` must be `active` (job fails otherwise), and it prints the live
   `/api/command-center` agreement + the readiness sweep.
3. Read the run logs to confirm green.

`mode: verify-only` runs just the checks (no code change).

### B. Manual on the VM (fallback)
```bash
bash /opt/trading-bot/scripts/deploy/update_vm.sh   # full-stack: bot + command-center
bash /opt/command-center/scripts/readiness_check.sh
```

---

## One-time setup: the self-hosted runner

Personal account (no org) → register the runner **per repo**. `update_vm.sh` is full-stack, so a
single runner in the bot repo can deploy everything; install one **here too** only if you want to
trigger “Deploy to VM” from this repo. On the VM, as the user that owns `/opt/*` (e.g. `alynx066`):

```bash
# Token + exact URL from: GitHub → this repo → Settings → Actions → Runners → New self-hosted runner
mkdir -p ~/actions-runner-cc && cd ~/actions-runner-cc
curl -o r.tar.gz -L https://github.com/actions/runner/releases/latest/download/actions-runner-linux-x64.tar.gz
tar xzf r.tar.gz
./config.sh --url https://github.com/SteveGuhlore/ai-operations-command-center --token <RUNNER_TOKEN> \
            --labels self-hosted --name tony-vm-cc --unattended
sudo ./svc.sh install $(whoami) && sudo ./svc.sh start
```

Passwordless sudo for the restarts (`/etc/sudoers.d/cc-deploy`):
```
alynx066 ALL=(root) NOPASSWD: /bin/systemctl restart tradingbot-api, /bin/systemctl restart tradingbot-web, /bin/systemctl restart cc-runner, /bin/systemctl restart tradingbot-offhours, /bin/systemctl restart tradingbot-watch
```

---

## Verify (after any deploy)
```bash
systemctl is-active cc-runner tradingbot-api
curl -s http://127.0.0.1:8001/api/command-center | python3 -m json.tool | grep -A6 '"agreement"'
bash /opt/command-center/scripts/readiness_check.sh
```

## Rollback
Prefer **revert** (preserves history):
```bash
cd /opt/command-center
git revert <bad-sha> && git push origin master
bash /opt/trading-bot/scripts/deploy/update_vm.sh
```
`git reset --hard` is destructive and blocked by the safety hook without explicit intent — last resort only.
