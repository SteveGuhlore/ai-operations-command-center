#!/usr/bin/env bash
# Syncs the vault to GitHub after each execution batch.
# Runs on Linux VPS only — silently skipped if not present.
set -euo pipefail

VAULT_DIR="/home/ubuntu/vault"
cd "$VAULT_DIR"

git add -A

# Exit cleanly if nothing to commit
if git diff --cached --quiet; then
    exit 0
fi

git commit -m "vault sync: $(date -u '+%Y-%m-%d %H:%M UTC')"
git push origin main
