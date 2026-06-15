#!/usr/bin/env bash
# promote_staging.sh — the promotion gate between an evening staging soak and main.
#
#   bash /opt/command-center/scripts/promote_staging.sh
#
# Runs, IN THE STAGING CHECKOUT:
#   1. the full pytest suite (staging venv)
#   2. scripts/readiness_check.sh with CC_DIR pointed at staging
#   3. a liveness probe of the staging dashboard (:8766)
#
# Only if ALL pass does it print the exact commands to fast-forward master and
# deploy production. It NEVER pushes, merges, or restarts anything itself.
set -uo pipefail

STAGING_DIR="${STAGING_DIR:-/opt/command-center-staging}"
PROD_DIR="${PROD_DIR:-/opt/command-center}"
STAGING_PORT="${STAGING_PORT:-8766}"
PY="$STAGING_DIR/.venv/bin/python"

fail() { echo; echo "PROMOTION BLOCKED: $1"; exit 1; }

[ -d "$STAGING_DIR" ]  || fail "no staging checkout at $STAGING_DIR (run scripts/setup_staging.sh first)"
[ -x "$PY" ]           || fail "no staging venv at $STAGING_DIR/.venv"

BRANCH="$(git -C "$STAGING_DIR" rev-parse --abbrev-ref HEAD)"
COMMIT="$(git -C "$STAGING_DIR" rev-parse --short HEAD)"
echo "Candidate: branch '$BRANCH' @ $COMMIT (soaked in $STAGING_DIR)"
[ "$BRANCH" != "master" ] && [ "$BRANCH" != "HEAD" ] || \
    fail "staging is on '$BRANCH' — check out the dev branch you soaked before promoting"

# "What you promote is what you soaked" applies to CODE, not runtime state: a live staging service
# constantly writes workspace/ (task files, ledgers) and bridge/ + vault/, so a plain `git diff`
# is always dirty. Check only for uncommitted CODE changes (everything outside those data dirs).
CODE_DIRTY="$(git -C "$STAGING_DIR" status --porcelain -- \
    ':(exclude)workspace' ':(exclude)bridge' ':(exclude)vault' 2>/dev/null)"
if [ -n "$CODE_DIRTY" ]; then
    fail "staging has uncommitted CODE changes (outside workspace/bridge/vault) — commit or discard them so what you promote is what you soaked:
$CODE_DIRTY"
fi

echo
echo "=== GATE 1/3: full pytest suite (clean worktree of the soaked commit) ==="
# Run the suite in a TEMPORARY CLEAN worktree of the exact soaked commit — never the live staging
# checkout. The running service's .env (CC_LLM_OFFLINE + the TONY_* path overrides, pulled in by
# runner/main.py's import-time load_dotenv) and its live workspace/ task files would otherwise leak
# into pytest and fail tests that assert the real LLM path / default paths / empty queues. A clean
# worktree tests the same code with none of that runtime contamination.
GATE_WT="$(mktemp -d)/gate"
git -C "$STAGING_DIR" worktree add --detach "$GATE_WT" HEAD >/dev/null 2>&1 || fail "could not create gate worktree"
_gate_cleanup() { git -C "$STAGING_DIR" worktree remove --force "$GATE_WT" >/dev/null 2>&1 || true; rmdir "$(dirname "$GATE_WT")" 2>/dev/null || true; }
trap _gate_cleanup EXIT
( cd "$GATE_WT" && "$PY" -m pytest -q ) || fail "pytest failed"   # fail() exits -> trap cleans the worktree
_gate_cleanup; trap - EXIT
echo "pytest: PASS"

echo
echo "=== GATE 2/3: readiness sweep against the STAGING instance ==="
CC_DIR="$STAGING_DIR" bash "$STAGING_DIR/scripts/readiness_check.sh" || fail "readiness_check.sh exited non-zero"
echo "readiness sweep: PASS (review the output above — the sweep is informational; eyeball anything odd)"

echo
echo "=== GATE 3/3: staging service liveness (:$STAGING_PORT) ==="
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$STAGING_PORT/" 2>/dev/null || echo 000)"
if [ "$HTTP_CODE" != "200" ]; then
    fail "staging dashboard not answering on :$STAGING_PORT (got $HTTP_CODE) — did the soak actually run? (systemctl status cc-runner-staging)"
fi
echo "dashboard :$STAGING_PORT -> 200 OK"

cat <<EOF

============================================================
 ALL GATES PASSED — '$BRANCH' @ $COMMIT is clear to promote.
============================================================
Nothing has been pushed or restarted. After market close, run BY HAND:

  # 1. Make the soaked branch reachable from origin (skip if already pushed)
  git -C $STAGING_DIR push origin $BRANCH

  # 2. Fast-forward master in the PRODUCTION checkout (ff-only: refuses
  #    anything that isn't exactly what staging soaked)
  git -C $PROD_DIR fetch origin
  git -C $PROD_DIR checkout master
  git -C $PROD_DIR merge --ff-only $COMMIT
  git -C $PROD_DIR push origin master

  # 3. Restart production on the new code (module cache means a restart is required)
  sudo systemctl restart cc-runner
  curl -s -o /dev/null -w 'prod dashboard -> %{http_code}\n' http://127.0.0.1:8765/

  # 4. Optional: stop the soak until next time
  sudo systemctl stop cc-runner-staging
============================================================
EOF
