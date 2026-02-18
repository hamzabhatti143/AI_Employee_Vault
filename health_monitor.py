"""
Health Monitor — checks PM2 processes, Odoo, and vault sync every 5 minutes.
Logs issues and sends notifications.
"""
import subprocess
import json
import time
import logging
import sys
from pathlib import Path
from datetime import datetime

# Setup imports from watchers dir
WATCHER_DIR = Path('/mnt/d/ai-employee-vault/watchers')
sys.path.insert(0, str(WATCHER_DIR))
for p in sorted((WATCHER_DIR / '.venv' / 'lib').glob('python*/site-packages'), reverse=True):
    sys.path.insert(0, str(p))
    break

from notifier import notify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [health-monitor] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

VAULT = Path('/mnt/d/ai-employee-vault')
LOG_FILE = VAULT / 'Logs' / 'health_alerts.log'
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Skip intentionally stopped processes
SKIP_PROCESSES = {'twitter-watcher'}

# Interval in seconds (5 minutes)
INTERVAL = 300


def check_pm2():
    """Check PM2 process statuses."""
    issues = []
    try:
        result = subprocess.run(
            ['pm2', 'jlist'], capture_output=True, text=True, timeout=15
        )
        procs = json.loads(result.stdout)
        for p in procs:
            name = p['name']
            status = p['pm2_env']['status']
            if name in SKIP_PROCESSES:
                continue
            if status != 'online':
                issues.append(f'{name} is {status}')
    except Exception as e:
        issues.append(f'PM2 check failed: {e}')
    return issues


def check_odoo():
    """Check if Odoo is reachable."""
    try:
        import requests
        resp = requests.get('http://localhost:8069/web/health', timeout=5)
        if resp.status_code != 200:
            return [f'Odoo returned status {resp.status_code}']
    except Exception:
        return ['Odoo is unreachable']
    return []


def check_vault_sync():
    """Check if vault has synced recently (last commit < 10 min ago)."""
    try:
        result = subprocess.run(
            ['git', '-C', str(VAULT), 'log', '-1', '--format=%ct'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ['Git log failed — repo may not be initialized']
        last_commit = int(result.stdout.strip())
        age_minutes = (time.time() - last_commit) / 60
        if age_minutes > 10:
            return [f'Vault sync may be stalled ({int(age_minutes)} min since last commit)']
    except Exception as e:
        return [f'Sync check failed: {e}']
    return []


def check_health():
    """Run all health checks."""
    issues = []
    issues.extend(check_pm2())
    issues.extend(check_odoo())
    issues.extend(check_vault_sync())
    return issues


def main():
    logger.info('Health Monitor started — checking every 5 minutes')
    while True:
        issues = check_health()
        if issues:
            logger.warning(f'Health issues: {issues}')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with LOG_FILE.open('a') as f:
                f.write(f'{timestamp}: {issues}\n')
            notify('Health Alert', '\n'.join(issues))
        else:
            logger.info('All systems healthy')
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
