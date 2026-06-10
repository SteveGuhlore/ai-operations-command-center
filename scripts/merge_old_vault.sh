#!/usr/bin/env bash
# merge_old_vault.sh — safely merge a pre-VM vault (a .zip of the old vault/ folder) into the
# live vault. ADD-ONLY: it never overwrites data the running machine produced (newer wins); the
# CRM is deliberately UNION-MERGED + deduped so leads from both sides survive. Fully reversible
# via the snapshot taken in step 1.
#
# Usage:  bash scripts/merge_old_vault.sh /tmp/vault.zip
set -euo pipefail

ZIP="${1:?usage: merge_old_vault.sh /path/to/vault.zip}"
CC="${CC_DIR:-/opt/command-center}"
VAULT="$CC/vault"
STAGE=/tmp/old-vault-stage

echo "== 1. snapshot current vault (rollback point) =="
bash "$CC/scripts/backup_vault.sh"

echo "== 2. extract $ZIP =="
rm -rf "$STAGE"; mkdir -p "$STAGE"
unzip -q "$ZIP" -d "$STAGE"
ROOT="$(dirname "$(find "$STAGE" -type d -name tickers | head -1)")"
[ -n "$ROOT" ] && [ -d "$ROOT" ] || { echo "ERROR: no vault root (a dir containing tickers/) found in the zip"; exit 1; }
echo "old vault root: $ROOT"

echo "== 3. survey (nothing changed yet) =="
only=$(comm -23 <(cd "$ROOT" && find . -type f | grep -v '/\.git/' | sort) <(cd "$VAULT" && find . -type f | sort) | wc -l)
both=$(comm -12 <(cd "$ROOT" && find . -type f | grep -v '/\.git/' | sort) <(cd "$VAULT" && find . -type f | sort) | wc -l)
echo "old-only files (will be ADDED):   $only"
echo "in-both files  (VM version KEPT): $both"

echo "== 4. merge CRM (union, deduped — both sides' leads survive) =="
if [ -f "$ROOT/outreach/crm.md" ]; then
  mkdir -p "$VAULT/outreach"
  touch "$VAULT/outreach/crm.md"
  python3 "$CC/scripts/merge_crm.py" "$ROOT/outreach/crm.md" "$VAULT/outreach/crm.md" "$VAULT/outreach/crm.md.tmp"
  mv "$VAULT/outreach/crm.md.tmp" "$VAULT/outreach/crm.md"
fi

echo "== 5. add-only merge of everything else (never overwrites VM-newer; skips .git/.obsidian) =="
rsync -a --ignore-existing --exclude='.git' --exclude='.obsidian' "$ROOT"/ "$VAULT"/

echo "== done =="
echo "CRM rows now:    $(grep -c '^| ' "$VAULT/outreach/crm.md")"
echo "vault files now: $(find "$VAULT" -type f | wc -l)"
echo "If anything looks wrong, restore the snapshot from /var/backups/cc-vault/ (newest .tar.gz)."
