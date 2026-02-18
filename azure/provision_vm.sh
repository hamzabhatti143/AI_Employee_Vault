#!/usr/bin/env bash
# provision_vm.sh — Run ON the Azure VM to install all dependencies
# Usage: chmod +x ~/provision_vm.sh && ~/provision_vm.sh
set -euo pipefail

echo "=== Provisioning Azure VM for AI Employee Vault ==="
echo ""

###############################################################################
# 1. Create 2GB Swap (critical for B1s with 1GB RAM)
###############################################################################
echo "--- 1/5: Creating 2GB swap ---"
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    # Tune swappiness for low-RAM server
    echo 'vm.swappiness=60' | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo "Swap created and enabled."
else
    echo "Swap already exists, skipping."
fi
free -h

###############################################################################
# 2. Install Docker + Docker Compose
###############################################################################
echo ""
echo "--- 2/5: Installing Docker ---"
if ! command -v docker &>/dev/null; then
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker "$USER"
    echo "Docker installed. You may need to log out/in for group to take effect."
else
    echo "Docker already installed."
fi

###############################################################################
# 3. Install Python 3.12 + venv
###############################################################################
echo ""
echo "--- 3/5: Installing Python 3.12 ---"
if ! command -v python3.12 &>/dev/null; then
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update
    sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
    echo "Python 3.12 installed."
else
    echo "Python 3.12 already installed."
fi
python3.12 --version

###############################################################################
# 4. Install Node.js via nvm + PM2
###############################################################################
echo ""
echo "--- 4/5: Installing Node.js + PM2 ---"
if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
fi

# Source nvm for current session
export NVM_DIR="$HOME/.nvm"
# shellcheck source=/dev/null
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

if ! command -v node &>/dev/null; then
    nvm install --lts
    echo "Node.js installed."
else
    echo "Node.js already installed: $(node --version)"
fi

if ! command -v pm2 &>/dev/null; then
    npm install -g pm2
    echo "PM2 installed."
else
    echo "PM2 already installed."
fi

###############################################################################
# 5. Install Claude CLI
###############################################################################
echo ""
echo "--- 5/5: Installing Claude CLI ---"
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
    echo "Claude CLI installed."
else
    echo "Claude CLI already installed."
fi

###############################################################################
# Install git (should be there, but just in case)
###############################################################################
sudo apt-get install -y git

###############################################################################
# Done
###############################################################################
echo ""
echo "==========================================="
echo "  PROVISIONING COMPLETE!"
echo "==========================================="
echo ""
echo "IMPORTANT: Log out and back in for Docker group to take effect:"
echo "  exit"
echo "  ssh -i ~/.ssh/id_rsa hamza@<VM_IP>"
echo ""
echo "Then run: chmod +x ~/deploy_vault.sh && ~/deploy_vault.sh"
echo ""
