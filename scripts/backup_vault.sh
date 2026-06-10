#!/usr/bin/env bash
# backup_vault.sh — snapshot the gitignored memory layer so it survives a disk loss or a fresh
# re-clone. vault/ (ticker memory, signal ledger, pattern library, agent learnings, CRM) and the
# task history are excluded from git on purpose (PII + churn), which means git NEVER backs them
# up. This does. Run it from cron nightly; safe to run anytime — it only reads and writes archives.
set -euo pipefail

CC_DIR="${CC_DIR:-/opt/command-center}"
DEST="${VAULT_BACKUP_DIR:-/var/backups/cc-vault}"
KEEP_DAYS="${VAULT_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$DEST"
ts="$(date +%Y%m%d-%H%M%S)"
archive="$DEST/cc-memory-$ts.tar.gz"

# vault/ is the memory layer; workspace/tasks is the task history (and the lead-prose source).
paths=(vault)
[ -d "$CC_DIR/workspace/tasks" ] && paths+=(workspace/tasks)

tar -czf "$archive" -C "$CC_DIR" "${paths[@]}"
echo "backup_vault: wrote $archive ($(du -h "$archive" | cut -f1))"

# Retain the most recent KEEP_DAYS days; prune older snapshots.
find "$DEST" -name 'cc-memory-*.tar.gz' -mtime +"$KEEP_DAYS" -delete
echo "backup_vault: current snapshots in $DEST:"
ls -1t "$DEST"/cc-memory-*.tar.gz
