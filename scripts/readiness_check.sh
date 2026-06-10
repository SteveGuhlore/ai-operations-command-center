#!/usr/bin/env bash
# readiness_check.sh — read-only health sweep across the pods, the scanner-bot tandem, the
# off-market research wave, and the nightly learning. NO side effects (stages no tasks, writes
# nothing). Run it anytime to confirm the system is ready.
CC="${CC_DIR:-/opt/command-center}"
cd "$CC" || { echo "no $CC"; exit 1; }
PY="$CC/.venv/bin/python"; [ -x "$PY" ] || PY=python3
line(){ printf '\n========== %s ==========\n' "$1"; }

line "SERVICES & CODE"
for s in cc-runner tradingbot-api tradingbot-web; do
  printf '%-22s %s\n' "$s:" "$(systemctl is-active "$s.service" 2>/dev/null || echo '(absent)')"
done
echo "code:   $(git log --oneline -1)"
echo "branch: $(git rev-parse --abbrev-ref HEAD)  (origin/master: $(git rev-parse --short origin/master 2>/dev/null))"
grep -n 'PROSPECTOR_PAUSED *=' runner/main.py | head -1

line "MARKET SESSION (drives the off-hours research lane)"
$PY -c "from runner.ledger.market_clock import market_session as m; print('session now:', m())" 2>&1 | tail -1

line "TONY POD + SUPPORTING AGENTS"
for a in market_research_worker debug_worker heavy_worker; do
  [ -f "agents/$a.md" ] && echo "agent def $a: OK" || echo "agent def $a: MISSING"
done
echo "-- last 6 Tony / market_scan tasks completed --"
ls -t workspace/tasks/done 2>/dev/null | grep -iE 'TONY|market' | head -6
echo "-- Tony/market tasks in failed/ (count) --"
ls workspace/tasks/failed 2>/dev/null | grep -iEc 'TONY|market'

line "SCANNER-BOT TANDEM (bridge ingestion)"
echo "-- newest bridge files the bot dropped --"
ls -lat bridge/tony-stocks/*.md 2>/dev/null | head -5 || echo "(no bridge files)"
echo "-- processed-keys dedup log --"
$PY -c "import json; d=json.load(open('workspace/logs/tony-bridge-processed.json')); print('processed keys:',len(d)); [print('   ',k) for k in sorted(d)[-6:]]" 2>&1 | tail -8
echo "-- bot's command_center_dir (MUST point at $CC) --"
grep -rIn "command_center_dir" /opt/trading-bot/config /opt/trading-bot/*.yaml /opt/trading-bot/.env 2>/dev/null | head -3 || echo "(config grep found nothing — check bot config manually)"
curl -s -o /dev/null -w "bot api :8001 -> %{http_code}\n" http://127.0.0.1:8001/ 2>/dev/null

line "OFF-MARKET RESEARCH WAVE (overnight)"
$PY -c "
from runner.bridge import research_wave as rw
print('next market open:', rw._next_open_date())
st = rw._read_state()
print('wave state:', st if st else '(nothing staged yet — will stage on the next closed-market cycle)')
" 2>&1 | tail -4
echo "-- research/intraday tasks queued right now --"
ls workspace/tasks/todo 2>/dev/null | grep -iE 'TONY|RW|research|wave' | head -8 || echo "(todo queue empty)"

line "NIGHTLY LEARNING"
$PY -c "from runner.scheduler.daily_jobs import daily_learning_due, weekly_sage_due; print('daily learning due now:', daily_learning_due()); print('weekly sage synthesis due:', weekly_sage_due())" 2>&1 | tail -2
echo "-- most recent learnings written --"
ls -t vault/learnings 2>/dev/null | head -5
echo "-- auto-calibration freshness across agent prompts --"
grep -rho "Updated 2026-[0-9-]*" agents/*.md 2>/dev/null | sort | uniq -c

line "VAULT / MEMORY / BACKUP"
echo "vault files: $(find vault -type f 2>/dev/null | wc -l)"
echo "CRM leads:   $(grep -c '^| ' vault/outreach/crm.md 2>/dev/null)"
echo "snapshots:   $(ls -1 /var/backups/cc-vault/*.tar.gz 2>/dev/null | wc -l) in /var/backups/cc-vault"
crontab -l 2>/dev/null | grep -q backup_vault && echo "nightly vault backup cron: OK" || echo "nightly vault backup cron: MISSING"

printf '\n========== sweep complete ==========\n'
