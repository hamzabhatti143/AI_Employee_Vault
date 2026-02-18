"""
Watchdog Monitor — checks PM2 processes every 60s, restarts any that aren't online.
Logs restarts to Logs/watchdog.log and sends notifications.
"""
import subprocess
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Add watchers dir to path so we can import notifier
import sys
sys.path.insert(0, str(Path(__file__).parent))

from notifier import notify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [watchdog] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

VAULT = Path('/mnt/d/ai-employee-vault')
LOG_FILE = VAULT / 'Logs' / 'watchdog.log'

# Processes to monitor — skip twitter-watcher (intentionally stopped)
MONITORED = {'gmail-watcher', 'wa-watcher', 'orchestrator', 'accounting-watcher'}

MAX_RESTARTS_PER_HOUR = 5  # per process, to avoid restart loops


def get_pm2_status():
    """Return dict of {name: status} for all PM2 processes."""
    try:
        result = subprocess.run(
            ['pm2', 'jlist'], capture_output=True, text=True, timeout=15
        )
        procs = json.loads(result.stdout)
        return {p['name']: p['pm2_env']['status'] for p in procs}
    except Exception as e:
        logger.error(f'Failed to get PM2 status: {e}')
        return {}


def restart_process(name):
    """Restart a PM2 process and log it."""
    logger.warning(f'{name} is not online — restarting')
    subprocess.run(['pm2', 'restart', name], capture_output=True, timeout=30)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open('a') as f:
        f.write(f'{timestamp} — restarted {name}\n')

    notify('Watchdog Alert', f'Restarted {name} (was not online)')


def main():
    logger.info(f'Watchdog started — monitoring: {", ".join(sorted(MONITORED))}')
    restart_counts = {name: [] for name in MONITORED}

    while True:
        status = get_pm2_status()
        if not status:
            logger.warning('Could not read PM2 status, skipping cycle')
            time.sleep(60)
            continue

        for name in MONITORED:
            proc_status = status.get(name)
            if proc_status is None:
                logger.info(f'{name} not found in PM2 — skipping')
                continue
            if proc_status == 'online':
                continue

            # Rate-limit restarts
            now = time.time()
            recent = [t for t in restart_counts[name] if now - t < 3600]
            restart_counts[name] = recent

            if len(recent) >= MAX_RESTARTS_PER_HOUR:
                logger.error(
                    f'{name} hit {MAX_RESTARTS_PER_HOUR} restarts/hour — '
                    f'skipping to avoid loop'
                )
                continue

            restart_process(name)
            restart_counts[name].append(now)

        time.sleep(60)


if __name__ == '__main__':
    main()
