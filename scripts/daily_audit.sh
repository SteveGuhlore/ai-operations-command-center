#!/usr/bin/env bash
# Tony Stocks — complete daily system audit.
# Run on the VM:  bash scripts/daily_audit.sh
# Read-only: checks the live system end-to-end (cycle, learning, memory, scorecard,
# verdict hygiene, queue, position protection/sizing, the 9:25 cron, research params).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
ok(){   echo "  [ OK ] $*"; }
warn(){ echo "  [WARN] $*"; }
bad(){  echo "  [FAIL] $*"; }
echo "============== TONY DAILY AUDIT — $(date) =============="

echo "[1] Runner cycling"
n=$(journalctl -u cc-runner.service --since "15 min ago" 2>/dev/null | grep -cE "No tasks|Dispatching")
[ "${n:-0}" -gt 0 ] && ok "cycling ($n hits/15min)" || bad "NOT cycling — check cc-runner.service"

echo "[2] Daily learning: hook fired AND improvement_loop actually produced output"
# grep -c (not -q): -q exits early and SIGPIPEs journalctl, which pipefail turns into a false WARN
hooks=$(journalctl -u cc-runner.service --since "2 days ago" 2>/dev/null | grep -ci "learning hook")
[ "${hooks:-0}" -gt 0 ] && ok "hook fired (${hooks}x in last 2 days)" || warn "no learning-hook log in 2 days"
latest=$(ls -t vault/learnings/*.md 2>/dev/null | head -1)
[ -n "$latest" ] && ok "synthesis output: $latest" \
  || bad "vault/learnings empty — nightly learning not producing (check GOOGLE_AI_API_KEY)"
overnight=$(ls -t vault/learnings/*-overnight.md 2>/dev/null | head -1)
[ -n "$overnight" ] && ok "improvement_loop summary: $overnight" \
  || warn "no *-overnight.md yet — improvement_loop hasn't written its own summary (it may only write when it changes an agent prompt; check: $PY scripts/improvement_loop.py)"
grep -q "GOOGLE_AI_API_KEY" .env 2>/dev/null && ok "GOOGLE_AI_API_KEY set" \
  || bad "GOOGLE_AI_API_KEY MISSING — nightly self-improvement can't run"

echo "[3] Memory growth"
echo "    tickers: $(ls vault/tickers/*.md 2>/dev/null | wc -l) | sessions today: $(ls vault/sessions/$(date +%F)/ 2>/dev/null | wc -l) | vault .md total: $(find vault -name '*.md' 2>/dev/null | wc -l)"
for f in vault/agents/market_research_worker/learned_rules.md vault/tony-stocks/pattern-library.md; do
  [ -f "$f" ] && ok "$(basename "$f"): $(stat -c%s "$f")b, mtime $(date -r "$f" +%F_%H:%M)" || warn "$f not written yet"
done

echo "[4] Scorecard (learning grounded in real outcomes)"
$PY -c "from runner.ledger.tony_scorecard import compute_record as r; x=r(); print('    status:',x.get('status'),'| graded:',x.get('graded'),'| win_rate:',x.get('win_rate'),'| calib:',x.get('calibration'))" 2>/dev/null || warn "scorecard read failed"

echo "[5] Verdict hygiene (should be ~one day's worth, NOT hundreds)"
$PY -c "
from runner.ledger.alpaca_paper import VERDICTS_FILE,_load
from collections import Counter
v=_load(VERDICTS_FILE); dates=sorted(set(x.get('date') for x in v if x.get('date')))
print('    count:',len(v),'| dates:',dates)
print('    BACKLOG — flush failed (multiple dates)' if len(dates)>1 else '    healthy (single day; count is fine even if large)')
" 2>/dev/null || warn "verdicts read failed"

echo "[6] Research queue (populates after the close via the wave)"
$PY -c "from runner.ledger.research_queue import read_queue; q=read_queue(); print('    candidates:',len(q.get('candidates',[])),'| target_open:',q.get('target_open'))" 2>/dev/null || warn "queue read failed"

echo "[7] Positions — protection + sizing"
curl -s http://127.0.0.1:8765/api/tony/book 2>/dev/null | $PY -c "
import sys,json,collections
try: b=json.load(sys.stdin)['book']
except Exception as e: print('    book read failed:',e); raise SystemExit(0)
from runner.ledger.alpaca_paper import ENTRY_NOTIONAL
pos=b.get('open_positions',[]) or []; orders=b.get('orders',[]) or []
stop=collections.defaultdict(float)
for o in orders:
    if o.get('side')=='sell' and o.get('stop_price') is not None: stop[o['symbol']]+=float(o.get('qty') or 0)
# Stops can only cover WHOLE shares (Alpaca rejects fractional legs), so a fractional position
# protected at int(qty) is BY DESIGN — only a stop covering less than the whole-share floor is
# a real problem. Report the three states separately so design-floor noise doesn't mask real risk.
naked, partial, frac_floor = [], [], []
for p in pos:
    q=float(p.get('qty') or 0); s=stop.get(p['symbol'],0); floor=int(q)
    if floor>=1 and s<=0: naked.append((p['symbol'],q))
    elif s<floor: partial.append((p['symbol'],f'{s:.0f}/{floor}'))
    elif s<q: frac_floor.append(p['symbol'])
over=[(p['symbol'],round(float(p['qty'])*float(p.get('current_price') or 0))) for p in pos if float(p.get('qty') or 0)*float(p.get('current_price') or 0) > 1.5*ENTRY_NOTIONAL]
print('    positions:',len(pos),'| equity:',b.get('equity'))
print('    TRULY NAKED (no stop at all):', naked or 'none')
print('    PARTIAL (stop < whole-share floor):', partial or 'none')
print('    fractional-floor (protected at int(qty), remainder unbracketable — by design):', frac_floor or 'none')
print('    OVERSIZED (>1.5x):', over or 'none')
" 2>/dev/null || warn "book/dashboard read failed"

echo "[8] Pre-open 9:25 cron + last reset"
crontab -l 2>/dev/null | grep -q "preopen" && ok "9:25 cron scheduled" || bad "preopen cron MISSING (verdicts won't flush)"
last=$(ls -t workspace/tasks/*/TONY-PREOPEN-* 2>/dev/null | head -1)
[ -n "$last" ] && echo "    last preopen deep-dive: $last" || warn "no TONY-PREOPEN task found yet"

echo "[9] Research params + deep-dive breadth"
$PY -c "
import os,json
from dotenv import load_dotenv; load_dotenv('.env')  # the runner reads .env — so must this check
from runner.ledger.deepdive_ledger import COOLDOWN_HOURS,LEDGER_FILE
from runner.bridge.tony_bridge import FANOUT_MAX
try: n=len(json.load(open(LEDGER_FILE)))
except Exception: n=0
print('    cooldown_h:',COOLDOWN_HOURS,'| fanout_max:',FANOUT_MAX,'| intraday_sweep:',os.environ.get('TONY_INTRADAY_SWEEP','off'))
print('    distinct names in cooldown ledger (today\'s breadth):',n)
" 2>/dev/null || warn "params read failed"
fanouts=$(journalctl -u cc-runner.service --since "30 min ago" 2>/dev/null | grep -ci "fan-out ticker")
echo "    fan-out spawns (last 30 min): ${fanouts:-0}  (with sweep on + market open, expect >0 as cooldowns free up)"

echo "============== END AUDIT =============="
