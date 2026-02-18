"""
Cloud Orchestrator — runs every 15 minutes, uses Claude CLI to process
Needs_Action/ items and draft responses in Pending_Approval/.
"""
import subprocess
import time
import logging
import os
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [cloud-orchestrator] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

VAULT = Path('/mnt/d/ai-employee-vault')
NEEDS_ACTION = VAULT / 'Needs_Action'
PENDING_APPROVAL = VAULT / 'Pending_Approval'
UPDATES = VAULT / 'Updates'
LOG_FILE = VAULT / 'Logs' / 'cloud_orchestrator.log'

# Ensure directories exist
PENDING_APPROVAL.mkdir(parents=True, exist_ok=True)
UPDATES.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Interval in seconds (15 minutes)
INTERVAL = 900


def get_needs_action_files():
    """Get list of .md files in Needs_Action/."""
    if not NEEDS_ACTION.exists():
        return []
    return sorted(NEEDS_ACTION.glob('*.md'))


def get_already_drafted():
    """Get set of original filenames that already have drafts."""
    drafted = set()
    for f in PENDING_APPROVAL.glob('*.md'):
        try:
            content = f.read_text()
            for line in content.splitlines():
                if line.startswith('original_file:'):
                    orig = line.split(':', 1)[1].strip()
                    drafted.add(orig)
                    break
        except Exception:
            pass
    return drafted


def run_claude(prompt):
    """Run Claude CLI with proper settings for headless PM2 execution."""
    # Must unset CLAUDECODE env var when spawning Claude CLI from within Claude session
    env = os.environ.copy()
    env.pop('CLAUDECODE', None)

    # Add nvm bin to PATH if needed
    nvm_bin = Path.home() / '.nvm' / 'versions' / 'node'
    if nvm_bin.exists():
        node_versions = sorted(nvm_bin.iterdir(), reverse=True)
        if node_versions:
            env['PATH'] = f"{node_versions[0] / 'bin'}:{env.get('PATH', '')}"

    try:
        result = subprocess.run(
            ['claude', '--print', '--model', 'haiku', prompt],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(VAULT),
            stdin=subprocess.DEVNULL,  # Prevents hanging in PM2
            env=env,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.error('Claude CLI timed out after 5 minutes')
        return None
    except FileNotFoundError:
        logger.error('Claude CLI not found — is it installed and in PATH?')
        return None
    except Exception as e:
        logger.error(f'Claude CLI error: {e}')
        return None


def process_items():
    """Process all Needs_Action items via Claude CLI."""
    files = get_needs_action_files()
    if not files:
        logger.info('No items in Needs_Action/')
        return

    already_drafted = get_already_drafted()
    new_files = [f for f in files if f.name not in already_drafted]

    if not new_files:
        logger.info(f'{len(files)} items in Needs_Action/ but all already have drafts')
        return

    logger.info(f'{len(new_files)} new items to process')

    # Read file contents for the prompt
    file_summaries = []
    for f in new_files[:10]:  # Process max 10 at a time
        try:
            content = f.read_text()[:2000]  # Truncate long files
            file_summaries.append(f"### {f.name}\n{content}")
        except Exception as e:
            logger.warning(f'Could not read {f.name}: {e}')

    if not file_summaries:
        return

    prompt = f"""You are the Cloud AI Agent. Follow the rules in .claude/CLOUD_SKILL.md strictly.

Here are {len(file_summaries)} items from Needs_Action/ that need drafts:

{'---'.join(file_summaries)}

For each item, output a draft response in this exact format:

=== DRAFT: <filename> ===
---
type: email_reply
target: <recipient>
original_file: <original filename>
drafted_at: {datetime.now().isoformat()}
---

<Your drafted response>

=== END DRAFT ===

Draft professional, concise responses. Do NOT send anything — only draft."""

    logger.info('Calling Claude CLI...')
    output = run_claude(prompt)

    if not output:
        logger.warning('No output from Claude CLI')
        return

    # Parse drafts from output
    drafts = output.split('=== DRAFT:')
    saved_count = 0

    for draft in drafts[1:]:  # Skip first empty split
        try:
            end_idx = draft.find('=== END DRAFT ===')
            if end_idx == -1:
                content = draft
            else:
                content = draft[:end_idx]

            # Extract filename from header
            header_end = content.find('===')
            if header_end != -1:
                filename_hint = content[:header_end].strip()
                content = content[header_end + 3:].strip()
            else:
                filename_hint = f'draft_{saved_count}'

            # Create safe filename
            safe_name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in filename_hint)
            draft_path = PENDING_APPROVAL / f'DRAFT_{safe_name}.md'

            draft_path.write_text(content)
            saved_count += 1
            logger.info(f'Saved draft: {draft_path.name}')

        except Exception as e:
            logger.warning(f'Failed to parse draft: {e}')

    # Update status
    status_content = f"""# Cloud Orchestrator Status

**Last run:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Items processed:** {len(file_summaries)}
**Drafts created:** {saved_count}
**Pending review:** {len(list(PENDING_APPROVAL.glob('*.md')))}
"""
    (UPDATES / 'CLOUD_STATUS.md').write_text(status_content)
    logger.info(f'Processed {len(file_summaries)} items, created {saved_count} drafts')

    # Log to file
    with LOG_FILE.open('a') as f:
        f.write(f'{datetime.now().isoformat()} — processed {len(file_summaries)} items, '
                f'{saved_count} drafts created\n')


def main():
    logger.info(f'Cloud Orchestrator started — checking every {INTERVAL}s')
    while True:
        try:
            process_items()
        except Exception as e:
            logger.error(f'Error in processing cycle: {e}')
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
