#!/usr/bin/env bash
# deploy_vault.sh — Run ON the Azure VM after provision_vm.sh
# Clones repo, sets up Python venv, configures Docker, PM2, cron
set -euo pipefail

VAULT_DIR="$HOME/ai-employee-vault"
REPO_URL="https://github.com/hamzabhatti143/AI_Employee_Vault.git"
OLD_PATH="/mnt/d/ai-employee-vault"
NEW_PATH="$VAULT_DIR"

# Source nvm
export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

echo "=== Deploying AI Employee Vault ==="
echo ""

###############################################################################
# 1. Clone Repository
###############################################################################
echo "--- 1/7: Cloning Repository ---"
if [ ! -d "$VAULT_DIR" ]; then
    git clone "$REPO_URL" "$VAULT_DIR"
    echo "Cloned to $VAULT_DIR"
else
    echo "Repo already exists, pulling latest..."
    cd "$VAULT_DIR" && git pull origin main --no-edit
fi

###############################################################################
# 2. Copy Secrets
###############################################################################
echo ""
echo "--- 2/7: Copying Secrets ---"
# .env file
if [ -f "$HOME/dot-env" ]; then
    cp "$HOME/dot-env" "$VAULT_DIR/watchers/.env"
    echo "Copied .env"
fi

# Gmail OAuth files
for f in "$HOME"/gmail_token.json "$HOME"/client_secret_*.json; do
    if [ -f "$f" ]; then
        cp "$f" "$VAULT_DIR/watchers/"
        echo "Copied $(basename "$f")"
    fi
done

###############################################################################
# 3. Bulk-Replace Paths
###############################################################################
echo ""
echo "--- 3/7: Replacing Paths ---"
cd "$VAULT_DIR"

# Replace in all relevant files (Python, shell, JS, JSON, MD)
find . -type f \( -name "*.py" -o -name "*.sh" -o -name "*.js" -o -name "*.json" -o -name "*.md" \) \
    -not -path "./.git/*" \
    -not -path "*/node_modules/*" \
    -not -path "*/.venv/*" \
    -exec grep -l "$OLD_PATH" {} \; 2>/dev/null | while read -r file; do
    sed -i "s|$OLD_PATH|$NEW_PATH|g" "$file"
    echo "  Updated: $file"
done

echo "Path replacement complete."

###############################################################################
# 4. Python Virtual Environment
###############################################################################
echo ""
echo "--- 4/7: Setting Up Python Venv ---"
if [ ! -d "$VAULT_DIR/watchers/.venv" ]; then
    python3.12 -m venv "$VAULT_DIR/watchers/.venv"
    echo "Venv created."
fi

# Install dependencies (skip playwright — not needed on cloud)
"$VAULT_DIR/watchers/.venv/bin/pip" install --upgrade pip
"$VAULT_DIR/watchers/.venv/bin/pip" install -r "$VAULT_DIR/watchers/requirements.txt" \
    --ignore-installed playwright 2>/dev/null || \
"$VAULT_DIR/watchers/.venv/bin/pip" install -r "$VAULT_DIR/watchers/requirements.txt"

echo "Python dependencies installed."

###############################################################################
# 5. Docker — Odoo + PostgreSQL with Memory Limits
###############################################################################
echo ""
echo "--- 5/7: Setting Up Docker Services ---"

# Create cloud-specific docker-compose with memory limits
cat > "$VAULT_DIR/odoo-docker-compose.yml" <<'COMPOSE'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: postgres
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo_secure_pass
    volumes:
      - odoo-db:/var/lib/postgresql/data
    restart: always
    deploy:
      resources:
        limits:
          memory: 150M
    mem_limit: 150m

  odoo:
    image: odoo:17
    depends_on: [db]
    ports: ['8069:8069']
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo_secure_pass
    volumes:
      - odoo-data:/var/lib/odoo
    restart: always
    deploy:
      resources:
        limits:
          memory: 400M
    mem_limit: 400m

volumes:
  odoo-db:
  odoo-data:
COMPOSE

# Start Docker services
cd "$VAULT_DIR"
docker compose -f odoo-docker-compose.yml up -d
echo "Odoo + PostgreSQL started."

###############################################################################
# 6. PM2 — Start Services
###############################################################################
echo ""
echo "--- 6/7: Starting PM2 Services ---"

# Copy ecosystem file
cp "$HOME/ecosystem.config.js" "$VAULT_DIR/ecosystem.config.js" 2>/dev/null || true

# Ensure required directories exist
mkdir -p "$VAULT_DIR/Needs_Action" "$VAULT_DIR/Approved" "$VAULT_DIR/Done" \
         "$VAULT_DIR/Rejected" "$VAULT_DIR/Pending_Approval" "$VAULT_DIR/Updates" \
         "$VAULT_DIR/Logs" "$VAULT_DIR/Briefings" "$VAULT_DIR/Accounting" \
         "$VAULT_DIR/CRM" "$VAULT_DIR/Sales" "$VAULT_DIR/Inventory" \
         "$VAULT_DIR/Plans/social" "$VAULT_DIR/wa_outbox"

cd "$VAULT_DIR"
pm2 start ecosystem.config.js
pm2 save

# Configure PM2 to start on boot
pm2 startup systemd -u "$USER" --hp "$HOME" | tail -1 | bash || true

echo "PM2 services started."

###############################################################################
# 7. Cron Jobs
###############################################################################
echo ""
echo "--- 7/7: Setting Up Cron Jobs ---"

VENV_PYTHON="$VAULT_DIR/watchers/.venv/bin/python"

# Build crontab
CRON_CONTENT=$(cat <<CRON
# AI Employee Vault — Cloud Cron Jobs
# Sync vault every 2 minutes
*/2 * * * * $VAULT_DIR/azure/sync_vault.sh >> $VAULT_DIR/Logs/sync.log 2>&1
# Log rotation — delete logs older than 90 days
0 2 * * * find $VAULT_DIR/Logs -name '*.json' -mtime +90 -delete
# CEO Briefing — Sunday 11 PM
0 23 * * 0 $VAULT_DIR/generate_briefing.sh >> $VAULT_DIR/Logs/briefing.log 2>&1
# Process inbox — daily 8 AM
0 8 * * * $VENV_PYTHON $VAULT_DIR/watchers/orchestrator.py --process-inbox >> $VAULT_DIR/Logs/cron_inbox.log 2>&1
# Generate LinkedIn post — Monday 9 AM
0 9 * * 1 $VENV_PYTHON $VAULT_DIR/watchers/orchestrator.py --generate-linkedin >> $VAULT_DIR/Logs/cron_linkedin.log 2>&1
# Watchdog — every 5 minutes
*/5 * * * * $VAULT_DIR/azure/watchdog.sh >> $VAULT_DIR/Logs/watchdog.log 2>&1
CRON
)

echo "$CRON_CONTENT" | crontab -

echo "Cron jobs installed."

###############################################################################
# Done
###############################################################################
echo ""
echo "==========================================="
echo "  VAULT DEPLOYED SUCCESSFULLY!"
echo "==========================================="
echo ""
echo "Verification commands:"
echo "  pm2 status                                    # Check watchers"
echo "  docker ps                                     # Check Odoo + Postgres"
echo "  curl -s http://localhost:8069/web/health       # Odoo health"
echo "  free -h                                        # Memory usage"
echo ""
echo "For Gmail OAuth:"
echo "  1. From local machine: ssh -L 8090:localhost:8090 hamza@<VM_IP>"
echo "  2. On VM: cd ~/ai-employee-vault/watchers && ../.venv/bin/python gmail_watcher.py"
echo "  3. Open http://localhost:8090 in your local browser"
echo ""
