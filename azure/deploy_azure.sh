#!/usr/bin/env bash
# deploy_azure.sh — Create Azure B1s VM for AI Employee Vault
# Run this from your LOCAL machine (WSL) with Azure CLI installed.
set -euo pipefail

###############################################################################
# Config
###############################################################################
RESOURCE_GROUP="rg-ai-employee"
LOCATION="eastus"
VM_NAME="ai-employee-vm"
VM_SIZE="Standard_B1s"
VM_IMAGE="Canonical:ubuntu-24_04-lts:server:latest"
ADMIN_USER="hamza"
DISK_SIZE_GB=30
SSH_KEY_PATH="$HOME/.ssh/id_rsa"
VAULT_ROOT="/mnt/d/ai-employee-vault"

###############################################################################
# Preflight checks
###############################################################################
echo "=== Azure VM Deployment for AI Employee Vault ==="
echo ""

if ! command -v az &>/dev/null; then
    echo "ERROR: Azure CLI not found. Install it:"
    echo "  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
    exit 1
fi

# Check login
if ! az account show &>/dev/null; then
    echo "Not logged in to Azure. Running 'az login'..."
    az login
fi

echo "Subscription: $(az account show --query name -o tsv)"
echo ""

# Generate SSH key if needed
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f "$SSH_KEY_PATH" -N ""
fi

###############################################################################
# Phase 1: Create Resource Group
###############################################################################
echo "--- Phase 1: Resource Group ---"
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output table

###############################################################################
# Phase 2: Create VM
###############################################################################
echo ""
echo "--- Phase 2: Create B1s VM ---"
VM_IP=$(az vm create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$VM_NAME" \
    --size "$VM_SIZE" \
    --image "$VM_IMAGE" \
    --admin-username "$ADMIN_USER" \
    --ssh-key-values "${SSH_KEY_PATH}.pub" \
    --os-disk-size-gb "$DISK_SIZE_GB" \
    --public-ip-sku Standard \
    --output tsv \
    --query publicIpAddress)

echo "VM created! Public IP: $VM_IP"

###############################################################################
# Phase 3: Open Ports
###############################################################################
echo ""
echo "--- Phase 3: Open Ports ---"
az vm open-port \
    --resource-group "$RESOURCE_GROUP" \
    --name "$VM_NAME" \
    --port 22 \
    --priority 1000 \
    --output none

az vm open-port \
    --resource-group "$RESOURCE_GROUP" \
    --name "$VM_NAME" \
    --port 8069 \
    --priority 1010 \
    --output none

az vm open-port \
    --resource-group "$RESOURCE_GROUP" \
    --name "$VM_NAME" \
    --port 80 \
    --priority 1020 \
    --output none

echo "Ports 22, 8069, 80 opened."

###############################################################################
# Phase 4: Copy provisioning scripts to VM
###############################################################################
echo ""
echo "--- Phase 4: Copy Scripts to VM ---"
scp -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" \
    "$VAULT_ROOT/azure/provision_vm.sh" \
    "$VAULT_ROOT/azure/deploy_vault.sh" \
    "$VAULT_ROOT/azure/ecosystem.config.js" \
    "$VAULT_ROOT/azure/sync_vault.sh" \
    "$VAULT_ROOT/azure/watchdog.sh" \
    "${ADMIN_USER}@${VM_IP}:~/"

###############################################################################
# Phase 5: Copy secrets to VM
###############################################################################
echo ""
echo "--- Phase 5: Copy Secrets ---"
scp -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" \
    "$VAULT_ROOT/watchers/.env" \
    "${ADMIN_USER}@${VM_IP}:~/dot-env"

# Copy Gmail OAuth files if they exist
for f in "$VAULT_ROOT"/watchers/gmail_token.json "$VAULT_ROOT"/watchers/client_secret_*.json; do
    if [ -f "$f" ]; then
        scp -i "$SSH_KEY_PATH" "$f" "${ADMIN_USER}@${VM_IP}:~/"
        echo "  Copied: $(basename "$f")"
    fi
done

###############################################################################
# Save connection info
###############################################################################
CONNECTION_FILE="$VAULT_ROOT/azure/connection.env"
cat > "$CONNECTION_FILE" <<EOF
AZURE_VM_IP=$VM_IP
AZURE_VM_USER=$ADMIN_USER
AZURE_RESOURCE_GROUP=$RESOURCE_GROUP
AZURE_VM_NAME=$VM_NAME
SSH_KEY=$SSH_KEY_PATH
EOF

echo ""
echo "==========================================="
echo "  VM CREATED SUCCESSFULLY!"
echo "==========================================="
echo "  IP Address : $VM_IP"
echo "  SSH        : ssh -i $SSH_KEY_PATH $ADMIN_USER@$VM_IP"
echo "  Saved to   : $CONNECTION_FILE"
echo ""
echo "NEXT STEPS:"
echo "  1. SSH into the VM:"
echo "     ssh -i $SSH_KEY_PATH $ADMIN_USER@$VM_IP"
echo ""
echo "  2. Run provisioning (installs Docker, Python, Node, PM2):"
echo "     chmod +x ~/provision_vm.sh && ~/provision_vm.sh"
echo ""
echo "  3. Run vault deployment (clones repo, sets up services):"
echo "     chmod +x ~/deploy_vault.sh && ~/deploy_vault.sh"
echo ""
echo "  4. For Gmail OAuth, SSH with port forwarding:"
echo "     ssh -L 8090:localhost:8090 -i $SSH_KEY_PATH $ADMIN_USER@$VM_IP"
echo "     cd ~/ai-employee-vault/watchers && ../.venv/bin/python gmail_watcher.py"
echo "     Then open http://localhost:8090 in your local browser."
echo ""
