#!/usr/bin/env bash
# sync_vault.sh — Bidirectional git sync between local/cloud and GitHub
# Works identically on both WSL and Azure VM.
# Cron: */2 * * * * /path/to/sync_vault.sh >> Logs/sync.log 2>&1
set -euo pipefail

# Auto-detect vault directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"

# If this script is in the vault root (old location), use that
if [ -f "$SCRIPT_DIR/Business_Goals.md" ]; then
    VAULT_DIR="$SCRIPT_DIR"
fi

cd "$VAULT_DIR"

# Stash any uncommitted changes during pull to avoid merge conflicts
git add -A
git diff --staged --quiet || git commit -m "Auto-sync: $(hostname) $(date +%Y-%m-%d\ %H:%M:%S)"

# Pull with rebase to keep history clean
git pull --rebase origin main 2>/dev/null || {
    echo "$(date): Pull failed, attempting merge..."
    git rebase --abort 2>/dev/null || true
    git pull origin main --no-edit
}

# Push any local commits
git push origin main 2>/dev/null || echo "$(date): Push failed (will retry next cycle)"
