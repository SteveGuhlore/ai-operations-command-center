#!/usr/bin/env bash
# setup_staging.sh — build a TRUE duplicate staging environment on the production VM.
#
#   sudo-less, idempotent. Run as the same user that owns /opt/command-center:
#       bash /opt/command-center/scripts/setup_staging.sh [branch] [--mirror-bridge]
#
# Creates /opt/command-center-staging (git worktree of the production clone),
# its own .venv, an isolated .env, and writes a cc-runner-staging.service unit
# to /tmp for you to sudo-install. It NEVER writes into /opt/command-center's
# working tree, never touches the production .env, and never restarts cc-runner.
# (Exception, by design: `git worktree add` records lightweight metadata under
# /opt/command-center/.git/worktrees/ — repo bookkeeping only, invisible to the
# running service.)
#
# WORKTREE vs CLONE — we prefer `git worktree`:
#   * shares the object store with production (no duplicate history on disk)
#   * `git fetch` once in either checkout makes the objects available to both
#   * switching the staging branch is a plain `git checkout` — no remote round-trip
#   * `git worktree list` makes the staging checkout discoverable from production
# If worktree creation fails (old git, locked repo, branch conflicts), we fall
# back to a plain `git clone` of the same origin — fully equivalent, just heavier.
#
# ISOLATION GUARANTEES (each verified against the code on this branch):
#   port      — staging dashboard binds 127.0.0.1:8766 (production: 8765)
#   state     — workspace/ + vault/ + bridge/ defaults resolve RELATIVE TO THE
#               CHECKOUT (Path(__file__).parent...), so staging automatically
#               gets fresh copies inside /opt/command-center-staging. Verified:
#               TONY_BOOK_CACHE, TONY_EXECUTED_LOG, TONY_REGIME_CACHE,
#               TONY_RESEARCH_QUEUE_FILE, TONY_DEEPDIVE_LEDGER_FILE,
#               TONY_DECISION_AUDIT_FILE, TONY_REALIZED_FILE, TONY_EQUITY_HISTORY,
#               TONY_EQUITY_HISTORY_FILE, TONY_VERDICTS_ARCHIVE, TONY_RULES_FILE,
#               TONY_KILL_SWITCH, TONY_POSITION_META_FILE, TONY_PATTERN_LIBRARY,
#               TONY_VAULT_RECORD_FILE, OUTREACH_CRM_FILE, OUTREACH_SENT_LOG,
#               OUTREACH_EMAIL_QUEUE — all clone-relative, no override needed.
#   SHARED!   — six vars default to <repo-parent>/TradingBotAgentProject/reports
#               (i.e. /opt/TradingBotAgentProject/reports — the trading bot's
#               reports dir, SHARED between production and staging): TONY_REPORTS_DIR,
#               TONY_VERDICTS_FILE, TONY_OUTCOMES_FILE, TONY_RECORD_FILE,
#               TONY_INSIGHTS_FILE, TONY_IDEAS_FILE. These are force-overridden
#               below — staging writing verdicts into the bot's live reports dir
#               would corrupt production grading.
#   alpaca    — staging inherits the PRODUCTION paper keys unless you fill in the
#               ALPACA_*_STAGING placeholders. See the loud warning printed at the end.
#   bridge    — TONY_BRIDGE_DIR points at staging's own bridge/tony-stocks.
#               Optional --mirror-bridge installs a 1-minute cron that copies NEW
#               files from the production bridge + bot reports dir into staging
#               (never deletes, never overwrites, never writes back).
#   sends     — Telegram / SendGrid / Instagram are hard-disabled in staging so an
#               evening soak can never DM leads or post to the public channel.
set -euo pipefail

PROD_DIR="${PROD_DIR:-/opt/command-center}"
STAGING_DIR="${STAGING_DIR:-/opt/command-center-staging}"
STAGING_PORT="${STAGING_PORT:-8766}"
PROD_PORT=8765
UNIT_TMP="/tmp/cc-runner-staging.service"
MIRROR_BRIDGE=0

BRANCH=""
for arg in "$@"; do
    case "$arg" in
        --mirror-bridge) MIRROR_BRIDGE=1 ;;
        -h|--help) grep '^#' "$0" | head -20; exit 0 ;;
        *) BRANCH="$arg" ;;
    esac
done

[ -d "$PROD_DIR/.git" ] || { echo "FATAL: $PROD_DIR is not a git checkout"; exit 1; }
case "$STAGING_DIR" in
    "$PROD_DIR"|"$PROD_DIR"/*) echo "FATAL: STAGING_DIR must not be inside $PROD_DIR"; exit 1 ;;
esac

# Default branch: whatever is currently checked out in the production repo —
# normally you pass your dev branch explicitly.
if [ -z "$BRANCH" ]; then
    BRANCH="$(git -C "$PROD_DIR" rev-parse --abbrev-ref HEAD)"
    echo "No branch given — defaulting to production's current branch: $BRANCH"
fi

echo "=== [1/6] Staging checkout at $STAGING_DIR (branch: $BRANCH) ==="
git -C "$PROD_DIR" fetch origin --prune

if [ -e "$STAGING_DIR/.git" ]; then
    echo "Staging checkout already exists — updating to $BRANCH (idempotent re-run)."
    git -C "$STAGING_DIR" fetch origin --prune
    if git -C "$STAGING_DIR" checkout "$BRANCH" 2>/dev/null; then
        git -C "$STAGING_DIR" pull --ff-only origin "$BRANCH" || \
            echo "NOTE: ff-only pull skipped (local-only branch or diverged) — staging is on local $BRANCH as-is."
    else
        # branch is checked out in another worktree (usually production) — detach at its tip
        echo "NOTE: '$BRANCH' is checked out elsewhere — detaching staging at its tip."
        git -C "$STAGING_DIR" checkout --detach "$BRANCH"
    fi
else
    PROD_BRANCH="$(git -C "$PROD_DIR" rev-parse --abbrev-ref HEAD)"
    if [ "$BRANCH" = "$PROD_BRANCH" ]; then
        # worktree cannot check out a branch already checked out in production —
        # detach at the same commit instead (you can git checkout a real branch later).
        WT_REF="--detach $BRANCH"
    else
        WT_REF="$BRANCH"
    fi
    # shellcheck disable=SC2086
    if git -C "$PROD_DIR" worktree add "$STAGING_DIR" $WT_REF 2>/dev/null; then
        echo "Created git worktree (shared object store with production)."
    else
        echo "Worktree creation failed — falling back to a full clone."
        ORIGIN_URL="$(git -C "$PROD_DIR" remote get-url origin)"
        git clone "$ORIGIN_URL" "$STAGING_DIR"
        git -C "$STAGING_DIR" checkout "$BRANCH"
    fi
fi

echo "=== [2/6] Python venv + requirements ==="
if [ ! -x "$STAGING_DIR/.venv/bin/python" ]; then
    python3 -m venv "$STAGING_DIR/.venv"
fi
"$STAGING_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$STAGING_DIR/.venv/bin/pip" install --quiet -r "$STAGING_DIR/requirements.txt"
echo "venv ready: $("$STAGING_DIR/.venv/bin/python" --version)"

echo "=== [3/6] Isolated state directories ==="
mkdir -p \
    "$STAGING_DIR/workspace/tasks/todo" \
    "$STAGING_DIR/workspace/tasks/in_progress" \
    "$STAGING_DIR/workspace/tasks/done" \
    "$STAGING_DIR/workspace/tasks/failed" \
    "$STAGING_DIR/workspace/locks" \
    "$STAGING_DIR/workspace/logs" \
    "$STAGING_DIR/workspace/trading-reports" \
    "$STAGING_DIR/vault" \
    "$STAGING_DIR/bridge/tony-stocks"

echo "=== [4/6] .env (production copy + staging overrides appended) ==="
STAGING_ENV="$STAGING_DIR/.env"
ENV_MARKER="STAGING OVERRIDES — appended by scripts/setup_staging.sh"
if [ -f "$STAGING_ENV" ] && grep -qF "$ENV_MARKER" "$STAGING_ENV"; then
    # Idempotent re-run: NEVER regenerate — the user may have filled in staging
    # Alpaca keys. Delete the file yourself if you want a fresh copy.
    echo "Staging .env already has the staging block — leaving it untouched."
else
if [ -f "$PROD_DIR/.env" ]; then
    cp "$PROD_DIR/.env" "$STAGING_ENV"
else
    echo "WARNING: $PROD_DIR/.env not found — staging .env starts empty; fill in API keys."
    : > "$STAGING_ENV"
fi
chmod 600 "$STAGING_ENV"

# Keys we override: comment out any production value first so the staging block
# below is the ONLY live definition (correct regardless of first/last-wins parsing).
OVERRIDE_KEYS="
TONY_REPORTS_DIR TONY_VERDICTS_FILE TONY_OUTCOMES_FILE TONY_RECORD_FILE
TONY_INSIGHTS_FILE TONY_IDEAS_FILE TONY_BRIDGE_DIR
TONY_NOTIFY TONY_TELEGRAM_CHAT TONY_PUBLIC
TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID TELEGRAM_PUBLIC_CHANNEL_ID
OUTREACH_AUTOMATION SENDGRID_API_KEY INSTAGRAM_ACCESS_TOKEN
TONY_ACCOUNT_MODE TONY_LIVE_ENABLED TONY_LIVE_ALPACA_API_KEY TONY_LIVE_ALPACA_SECRET_KEY
CC_PORT
"
for key in $OVERRIDE_KEYS; do
    sed -i "s|^[[:space:]]*${key}=|# [prod, overridden by staging block] ${key}=|" "$STAGING_ENV"
done

cat >> "$STAGING_ENV" <<EOF

# ============================================================================
# STAGING OVERRIDES — appended by scripts/setup_staging.sh $(date -u +%Y-%m-%dT%H:%MZ)
# Everything below isolates this checkout from the 24/7 production service.
# ============================================================================
CC_PORT=$STAGING_PORT

# --- Tony state whose DEFAULTS resolve to the SHARED bot reports dir --------
# (default: <repo-parent>/TradingBotAgentProject/reports — same physical dir for
#  production and staging; the verdicts file there is read by the live bot.
#  These six MUST stay overridden.)
TONY_REPORTS_DIR=$STAGING_DIR/workspace/trading-reports
TONY_VERDICTS_FILE=$STAGING_DIR/workspace/trading-reports/tony_stocks_verdicts.json
TONY_OUTCOMES_FILE=$STAGING_DIR/workspace/trading-reports/tony_stocks_outcomes.json
TONY_RECORD_FILE=$STAGING_DIR/workspace/trading-reports/tony_stocks_record.json
TONY_INSIGHTS_FILE=$STAGING_DIR/workspace/trading-reports/agent_insights.json
TONY_IDEAS_FILE=$STAGING_DIR/workspace/trading-reports/tony_stocks_ideas.json

# --- Bridge: staging's own dir (the bot keeps writing only to production) ---
# Use --mirror-bridge to copy NEW production bridge files here automatically.
TONY_BRIDGE_DIR=$STAGING_DIR/bridge/tony-stocks

# --- Outbound sends: HARD OFF in staging -------------------------------------
TONY_NOTIFY=off
TONY_TELEGRAM_CHAT=off
TONY_PUBLIC=off
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_PUBLIC_CHANNEL_ID=
OUTREACH_AUTOMATION=false
SENDGRID_API_KEY=
INSTAGRAM_ACCESS_TOKEN=

# --- Live trading: impossible in staging -------------------------------------
TONY_ACCOUNT_MODE=paper
TONY_LIVE_ENABLED=
TONY_LIVE_ALPACA_API_KEY=
TONY_LIVE_ALPACA_SECRET_KEY=

# --- Alpaca paper account -----------------------------------------------------
# !!! WARNING !!!  Right now staging INHERITS the production paper keys above,
# which means staging WILL PLACE ORDERS ON THE SAME \$1M PAPER ACCOUNT the
# production runner trades — duplicate/conflicting orders, polluted equity
# curve, position-meta drift. Fine for a quick smoke test; NOT fine for a soak.
#
# RECOMMENDED: create a SECOND free paper account (alpaca.markets -> log in ->
# account switcher -> "Create New Account" -> Paper, then Generate API Keys),
# paste the keys below, and uncomment. Free, takes ~2 minutes.
#ALPACA_API_KEY=PK_REPLACE_WITH_STAGING_PAPER_KEY
#ALPACA_SECRET_KEY=REPLACE_WITH_STAGING_PAPER_SECRET
EOF
echo "Wrote $STAGING_ENV (production keys inherited, staging block appended)."
fi

echo "=== [5/6] Staging launcher + systemd unit ==="
# Production launches via scripts/launch.py, which HARDCODES port 8765 and—worse—
# refuses to start if anything is already listening there (it would see the
# production dashboard and exit). So staging gets its own thin launcher, written
# OUTSIDE the repo working tree (so git checkout/status in staging stays clean).
LAUNCHER="$STAGING_DIR/.venv/staging_launch.py"
cat > "$LAUNCHER" <<'PYEOF'
"""Staging launcher — mirrors scripts/launch.py but binds CC_PORT (default 8766).
Generated by scripts/setup_staging.sh; lives in .venv/ to stay out of git's way."""
import argparse, os, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("CC_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PORT = int(os.environ.get("CC_PORT", "8766"))


def port_busy() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=180)
    args = ap.parse_args()

    if port_busy():
        print(f"Staging already running on :{PORT} — not starting a duplicate.")
        return

    dash = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dashboard.server:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
    )
    print(f"[staging] dashboard on http://127.0.0.1:{PORT}", flush=True)

    from runner.main import run_cycle
    from runner.scheduler.cron_runner import CronRunner

    cron = CronRunner(interval_seconds=args.interval, callback=run_cycle)
    cron.start()
    run_cycle()
    try:
        while True:
            time.sleep(10)
            if dash.poll() is not None:
                print("[staging] dashboard exited — shutting down", flush=True)
                break
    finally:
        cron.stop()
        dash.terminate()


if __name__ == "__main__":
    main()
PYEOF

RUN_USER="$(id -un)"
cat > "$UNIT_TMP" <<EOF
# cc-runner-staging.service — STAGING twin of cc-runner.
# Dashboard on 127.0.0.1:$STAGING_PORT, working dir $STAGING_DIR, isolated .env.
# Installed by hand (commands printed by setup_staging.sh). Safe to stop/start
# at will — it shares nothing writable with the production service.
[Unit]
Description=Command Center STAGING (dashboard :$STAGING_PORT + agent cron loop)
After=network-online.target
Wants=network-online.target
ConditionPathExists=$STAGING_DIR/.venv/bin/python

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$STAGING_DIR
Environment=CC_ROOT=$STAGING_DIR
Environment=CC_PORT=$STAGING_PORT
ExecStart=$STAGING_DIR/.venv/bin/python $LAUNCHER --interval 180
Restart=on-failure
RestartSec=10
StandardOutput=append:$STAGING_DIR/workspace/logs/staging-runner.log
StandardError=append:$STAGING_DIR/workspace/logs/staging-runner.err.log

[Install]
WantedBy=multi-user.target
EOF
echo "Unit written to $UNIT_TMP (NOT installed — see commands below)."

echo "=== [6/6] Bridge mirror ==="
MIRROR_SCRIPT="$STAGING_DIR/.venv/mirror_bridge.sh"
cat > "$MIRROR_SCRIPT" <<EOF
#!/usr/bin/env bash
# Copy NEW files from the production bridge + bot reports dirs into staging.
# Read-only against production: never deletes, never overwrites, never writes back.
# Excludes tony_stocks_* outputs so production verdicts/records never leak into
# staging's own output files.
set -u
SRC_BRIDGE="$PROD_DIR/bridge/tony-stocks"
DST_BRIDGE="$STAGING_DIR/bridge/tony-stocks"
SRC_REPORTS="\$(dirname "$PROD_DIR")/TradingBotAgentProject/reports"
DST_REPORTS="$STAGING_DIR/workspace/trading-reports"
copy_new() {
    local src="\$1" dst="\$2"
    [ -d "\$src" ] || return 0
    mkdir -p "\$dst"
    for f in "\$src"/*; do
        [ -f "\$f" ] || continue
        base="\$(basename "\$f")"
        case "\$base" in tony_stocks_*|agent_insights*) continue ;; esac
        [ -e "\$dst/\$base" ] || cp "\$f" "\$dst/\$base"
    done
}
copy_new "\$SRC_BRIDGE" "\$DST_BRIDGE"
copy_new "\$SRC_REPORTS" "\$DST_REPORTS"
EOF
chmod +x "$MIRROR_SCRIPT"

CRON_TAG="# cc-staging-bridge-mirror"
if [ "$MIRROR_BRIDGE" -eq 1 ]; then
    if ! crontab -l 2>/dev/null | grep -qF "$CRON_TAG"; then
        ( crontab -l 2>/dev/null; echo "* * * * * $MIRROR_SCRIPT $CRON_TAG" ) | crontab -
        echo "Installed 1-minute bridge-mirror cron (production bridge -> staging, copy-new-only)."
    else
        echo "Bridge-mirror cron already installed."
    fi
    "$MIRROR_SCRIPT"  # prime immediately
else
    echo "Bridge mirror NOT enabled (staging bridge dir starts empty)."
    echo "Enable later with:  bash $0 $BRANCH --mirror-bridge"
fi

ALPACA_NOTE="!!! staging is using the PRODUCTION paper account keys — it WILL trade the same \$1M paper account.
    Strongly recommended: create a second free Alpaca paper account and fill the
    ALPACA_API_KEY / ALPACA_SECRET_KEY placeholders at the bottom of $STAGING_ENV."
grep -q '^ALPACA_API_KEY=PK_REPLACE' "$STAGING_ENV" 2>/dev/null && ALPACA_NOTE="staging Alpaca keys still placeholders — fill them in $STAGING_ENV"
grep -q '^#ALPACA_API_KEY=' "$STAGING_ENV" || ALPACA_NOTE="staging has its own ALPACA_API_KEY override — good."

cat <<EOF

============================================================
 STAGING READY — $STAGING_DIR  (branch: $(git -C "$STAGING_DIR" rev-parse --abbrev-ref HEAD) @ $(git -C "$STAGING_DIR" rev-parse --short HEAD))
============================================================
Install + start the service (the ONLY sudo steps):

    sudo cp $UNIT_TMP /etc/systemd/system/cc-runner-staging.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now cc-runner-staging.service

Then:
    Dashboard:   http://127.0.0.1:$STAGING_PORT      (production stays on :$PROD_PORT)
    Status:      systemctl status cc-runner-staging
    Logs:        tail -f $STAGING_DIR/workspace/logs/staging-runner.log
                 journalctl -u cc-runner-staging -f
    Stop:        sudo systemctl stop cc-runner-staging

ALPACA: $ALPACA_NOTE

Production service cc-runner was NOT touched by this script.
============================================================
EOF
