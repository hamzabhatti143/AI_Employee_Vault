// ecosystem.config.js — PM2 process configuration for Azure VM
// WhatsApp watcher is excluded (stays on local WSL — needs Playwright/Chromium)

const HOME = process.env.HOME || '/home/hamza';
const VAULT = `${HOME}/ai-employee-vault`;
const PYTHON = `${VAULT}/watchers/.venv/bin/python`;

module.exports = {
  apps: [
    {
      name: 'gmail-watcher',
      script: `${VAULT}/watchers/gmail_watcher.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 10000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
    {
      name: 'accounting-watcher',
      script: `${VAULT}/watchers/accounting_watcher.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 10000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
    {
      name: 'social-watcher',
      script: `${VAULT}/watchers/social_watcher.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 10000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
    {
      name: 'cloud-orchestrator',
      script: `${VAULT}/cloud_orchestrator.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 10000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
    {
      name: 'local-orchestrator',
      script: `${VAULT}/local_orchestrator.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 10000,
      max_restarts: 10,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
    {
      name: 'health-monitor',
      script: `${VAULT}/health_monitor.py`,
      interpreter: PYTHON,
      cwd: VAULT,
      restart_delay: 30000,
      max_restarts: 5,
      autorestart: true,
      env: {
        PYTHONPATH: `${VAULT}/watchers`,
      },
    },
  ],
};
