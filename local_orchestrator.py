"""
Local Orchestrator — monitors Pending_Approval/ for cloud-drafted items,
notifies the user, and processes approved actions via Claude CLI.

Works alongside the existing watchers/orchestrator.py which handles Approved/ execution.
"""
import os
import subprocess
import time
import shutil
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

from dotenv import load_dotenv
load_dotenv(WATCHER_DIR / '.env')

from notifier import notify
import audit_logger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [local-orchestrator] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

VAULT = Path('/mnt/d/ai-employee-vault')
PENDING = VAULT / 'Pending_Approval'
APPROVED = VAULT / 'Approved'
DONE = VAULT / 'Done'
LOG_FILE = VAULT / 'Logs' / 'local_orchestrator.log'

CLAUDE_BIN = '/home/hamza/.nvm/versions/node/v24.13.1/bin/claude'

# Track which drafts we've already notified about
notified_drafts = set()

# Ensure directories exist
for d in [PENDING, APPROVED, DONE, LOG_FILE.parent]:
    d.mkdir(parents=True, exist_ok=True)


def check_new_cloud_drafts():
    """Check for new drafts in Pending_Approval/ and notify user."""
    for draft in PENDING.glob('*.md'):
        if draft.name not in notified_drafts:
            logger.info(f'New draft from cloud: {draft.name}')
            notify('AI Employee — New Draft', f'Review: {draft.name}')
            notified_drafts.add(draft.name)

    # Also check subdirectories (email/, social/, payments/)
    for subdir in ['email', 'social', 'payments']:
        draft_folder = PENDING / subdir
        draft_folder.mkdir(exist_ok=True)
        for draft in draft_folder.glob('*.md'):
            key = f'{subdir}/{draft.name}'
            if key not in notified_drafts:
                logger.info(f'New draft from cloud: {key}')
                notify('AI Employee — New Draft', f'Review: {draft.name} ({subdir})')
                notified_drafts.add(key)


def run_claude(prompt):
    """Run Claude CLI with proper headless settings."""
    env = os.environ.copy()
    env.pop('CLAUDECODE', None)

    nvm_bin = Path.home() / '.nvm' / 'versions' / 'node'
    if nvm_bin.exists():
        node_versions = sorted(nvm_bin.iterdir(), reverse=True)
        if node_versions:
            env['PATH'] = f"{node_versions[0] / 'bin'}:{env.get('PATH', '')}"

    try:
        result = subprocess.run(
            [CLAUDE_BIN, '--print', '--model', 'haiku', prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(VAULT),
            stdin=subprocess.DEVNULL,
            env=env,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error('Claude CLI timed out')
        return None
    except Exception as e:
        logger.error(f'Claude CLI error: {e}')
        return None


def process_approved():
    """Execute approved actions via Claude CLI and move to Done/."""
    for approved in sorted(APPROVED.glob('*.md')):
        logger.info(f'Executing approved: {approved.name}')

        try:
            content = approved.read_text()[:3000]
        except Exception as e:
            logger.error(f'Could not read {approved.name}: {e}')
            continue

        prompt = f"""You have access to MCP tools (send_email, reply_to_email, send_whatsapp,
post_facebook, post_instagram, create_invoice, create_crm_lead, etc.)

Execute this approved action:

{content}

After executing, summarize what you did."""

        result = run_claude(prompt)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if result:
            logger.info(f'Completed: {approved.name}')
            audit_logger.log_action(
                action_type='approved_execution',
                actor='local-orchestrator',
                target=approved.name,
                parameters={'content_preview': content[:200]},
                approval_status='approved',
                result=result[:500],
            )
        else:
            logger.warning(f'No result for: {approved.name}')
            result = 'No output from Claude CLI'

        # Append result to the file and move to Done
        with approved.open('a') as f:
            f.write(f'\n\n---\n**Executed:** {timestamp}\n**Result:** {result}\n')

        dest = DONE / approved.name
        if dest.exists():
            dest = DONE / f'{approved.stem}_{datetime.now().strftime("%H%M%S")}{approved.suffix}'
        shutil.move(str(approved), str(dest))
        logger.info(f'Moved to Done: {dest.name}')

        # Log to file
        with LOG_FILE.open('a') as f:
            f.write(f'{timestamp} — executed {approved.name}\n')


def main():
    logger.info('Local Orchestrator started — checking every 30s')
    while True:
        try:
            check_new_cloud_drafts()
            process_approved()
        except Exception as e:
            logger.error(f'Error in cycle: {e}')
        time.sleep(30)


if __name__ == '__main__':
    main()
