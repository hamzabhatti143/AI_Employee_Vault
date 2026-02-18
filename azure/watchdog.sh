#!/usr/bin/env bash
# watchdog.sh — Checks health of all services, restarts if needed
# Cron: */5 * * * * /path/to/watchdog.sh >> Logs/watchdog.log 2>&1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_PREFIX="$(date '+%Y-%m-%d %H:%M:%S') [watchdog]"

# Source nvm for PM2 access
export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

ISSUES=0

###############################################################################
# Check Docker containers (Odoo + PostgreSQL)
###############################################################################
if ! docker ps --format '{{.Names}}' | grep -q 'odoo'; then
    echo "$LOG_PREFIX WARNING: Odoo container not running. Restarting..."
    cd "$VAULT_DIR" && docker compose -f odoo-docker-compose.yml up -d
    ISSUES=$((ISSUES + 1))
fi

if ! docker ps --format '{{.Names}}' | grep -q 'db'; then
    echo "$LOG_PREFIX WARNING: PostgreSQL container not running. Restarting..."
    cd "$VAULT_DIR" && docker compose -f odoo-docker-compose.yml up -d
    ISSUES=$((ISSUES + 1))
fi

###############################################################################
# Check Odoo HTTP health
###############################################################################
if ! curl -sf http://localhost:8069/web/health > /dev/null 2>&1; then
    echo "$LOG_PREFIX WARNING: Odoo health check failed."
    ISSUES=$((ISSUES + 1))
fi

###############################################################################
# Check PM2 processes
###############################################################################
EXPECTED_PROCESSES=("gmail-watcher" "accounting-watcher" "social-watcher" "cloud-orchestrator" "local-orchestrator" "health-monitor")

for proc in "${EXPECTED_PROCESSES[@]}"; do
    STATUS=$(pm2 jlist 2>/dev/null | python3 -c "
import json, sys
procs = json.load(sys.stdin)
for p in procs:
    if p['name'] == '$proc':
        print(p['pm2_env']['status'])
        break
else:
    print('missing')
" 2>/dev/null || echo "error")

    if [ "$STATUS" != "online" ]; then
        echo "$LOG_PREFIX WARNING: $proc is $STATUS. Restarting..."
        pm2 restart "$proc" 2>/dev/null || pm2 start "$VAULT_DIR/ecosystem.config.js" --only "$proc"
        ISSUES=$((ISSUES + 1))
    fi
done

###############################################################################
# Check disk space (warn if > 80%)
###############################################################################
DISK_USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "$LOG_PREFIX WARNING: Disk usage at ${DISK_USAGE}%"
    ISSUES=$((ISSUES + 1))
fi

###############################################################################
# Check memory (warn if swap > 75% used)
###############################################################################
SWAP_TOTAL=$(free -m | awk '/Swap:/ {print $2}')
SWAP_USED=$(free -m | awk '/Swap:/ {print $3}')
if [ "$SWAP_TOTAL" -gt 0 ]; then
    SWAP_PCT=$((SWAP_USED * 100 / SWAP_TOTAL))
    if [ "$SWAP_PCT" -gt 75 ]; then
        echo "$LOG_PREFIX WARNING: Swap usage at ${SWAP_PCT}% (${SWAP_USED}M/${SWAP_TOTAL}M)"
        ISSUES=$((ISSUES + 1))
    fi
fi

###############################################################################
# Summary
###############################################################################
if [ "$ISSUES" -eq 0 ]; then
    # Only log every 12th run (once/hour) if healthy to reduce log noise
    MINUTE=$(date +%M)
    if [ "$((MINUTE % 60))" -lt 5 ]; then
        echo "$LOG_PREFIX OK: All services healthy."
    fi
fi
