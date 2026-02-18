"""Orchestrator: watches /Approved folder and executes actions via Claude CLI.

Usage:
    python orchestrator.py                    # Normal mode: watch /Approved in a loop
    python orchestrator.py --process-inbox    # One-shot: classify /Needs_Action and exit
    python orchestrator.py --generate-linkedin # One-shot: generate weekly LinkedIn post
"""

import argparse
import json
import os
import sys
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

# Add watchers dir and venv site-packages so gmail_utils/whatsapp_utils can be imported
WATCHER_DIR = Path(__file__).parent
sys.path.insert(0, str(WATCHER_DIR))
_venv_sp = WATCHER_DIR / '.venv' / 'lib'
for p in sorted(_venv_sp.glob('python*/site-packages'), reverse=True):
    sys.path.insert(0, str(p))
    break

import audit_logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

VAULT = Path('/mnt/d/ai-employee-vault')
NEEDS_ACTION = VAULT / 'Needs_Action'
APPROVED = VAULT / 'Approved'
PENDING_APPROVAL = VAULT / 'Pending_Approval'
PLANS = VAULT / 'Plans'
DONE = VAULT / 'Done'
LOGS = VAULT / 'Logs'
DASHBOARD = VAULT / 'Dashboard.md'
CLAUDE_BIN = '/home/hamza/.nvm/versions/node/v24.13.1/bin/claude'


def execute_approved(filepath):
    """Read an approved action file and execute it via Claude CLI."""
    content = filepath.read_text()
    logging.info(f'Executing: {filepath.name}')

    prompt = (
        f"You are an AI employee assistant. Analyze the following approved action and decide what to do.\n"
        f"Respond in this exact JSON format (no markdown, no backticks):\n"
        f'{{"action": "reply_email"|"send_email"|"send_whatsapp"|"create_invoice"|"create_crm_lead"|"create_sale_order"|"update_crm_stage"|"no_action", '
        f'"to": "recipient", "subject": "subject", "body": "message body", "message_id": "id if replying", '
        f'"partner_name": "Odoo partner name", "lines": [{{"description":"item","quantity":1,"price_unit":100}}], '
        f'"lead_name": "CRM lead name", "stage_name": "stage name", '
        f'"expected_revenue": 0, "lead_type": "opportunity|lead", '
        f'"reason": "brief explanation"}}\n\n'
        f"If this is an automated notification that needs no response, use \"no_action\".\n"
        f"For Odoo actions: create_invoice needs partner_name + lines, create_crm_lead needs lead_name + partner_name, "
        f"create_sale_order needs partner_name + lines (with product_name), update_crm_stage needs lead_name + stage_name.\n\n"
        f"---\n{content}\n---"
    )

    # Clean env so Claude CLI doesn't think it's nested inside another session
    clean_env = {k: v for k, v in os.environ.items() if k != 'CLAUDECODE'}
    # Ensure node/nvm bin is in PATH for Claude CLI
    nvm_bin = '/home/hamza/.nvm/versions/node/v24.13.1/bin'
    if nvm_bin not in clean_env.get('PATH', ''):
        clean_env['PATH'] = nvm_bin + ':' + clean_env.get('PATH', '')

    try:
        # Use Claude CLI without MCP tools — just for decision making
        result = subprocess.run(
            [CLAUDE_BIN, '--print', '--model', 'haiku', '-p', prompt],
            cwd=str(VAULT), env=clean_env,
            capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL,
        )

        output = result.stdout.strip()
        status = 'completed' if result.returncode == 0 else 'failed'

        # Parse and execute the action
        if status == 'completed' and output:
            try:
                import json as _json
                # Strip markdown code fences if present
                clean = output.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1] if '\n' in clean else clean[3:]
                    clean = clean.rsplit('```', 1)[0].strip()
                decision = _json.loads(clean)
                action = decision.get('action', 'no_action')

                if action == 'reply_email':
                    import gmail_utils
                    gmail_utils.reply_to_email(decision['message_id'], decision['body'])
                    output = f"Replied to email {decision['message_id']}: {decision['reason']}"
                    audit_logger.log_action("reply_email", "orchestrator", decision['message_id'], {"source": filepath.name}, "approved", "success")
                elif action == 'send_email':
                    import gmail_utils
                    gmail_utils.send_email(decision['to'], decision['subject'], decision['body'])
                    output = f"Sent email to {decision['to']}: {decision['reason']}"
                    audit_logger.log_action("send_email", "orchestrator", decision['to'], {"subject": decision['subject'], "source": filepath.name}, "approved", "success")
                elif action == 'send_whatsapp':
                    import whatsapp_utils
                    whatsapp_utils.send_message(decision['to'], decision['body'])
                    output = f"Sent WhatsApp to {decision['to']}: {decision['reason']}"
                    audit_logger.log_action("send_whatsapp", "orchestrator", decision['to'], {"source": filepath.name}, "approved", "success")
                elif action == 'create_invoice':
                    import odoo_utils
                    inv = odoo_utils.create_invoice(decision['partner_name'], decision['lines'])
                    output = f"Created invoice {inv['name']}: ${inv['amount_total']} - {decision['reason']}"
                    audit_logger.log_action("create_invoice", "orchestrator", decision['partner_name'], {"amount": inv['amount_total'], "source": filepath.name}, "approved", "success")
                elif action == 'create_crm_lead':
                    import odoo_utils
                    lead = odoo_utils.create_crm_lead(
                        decision.get('lead_name', decision.get('subject', 'New Lead')),
                        partner_name=decision.get('partner_name'),
                        expected_revenue=decision.get('expected_revenue', 0),
                        description=decision.get('body', ''),
                        lead_type=decision.get('lead_type', 'opportunity'),
                    )
                    output = f"Created CRM lead: {lead['name']} - {decision['reason']}"
                    audit_logger.log_action("create_crm_lead", "orchestrator", lead['name'], {"source": filepath.name}, "approved", "success")
                elif action == 'create_sale_order':
                    import odoo_utils
                    so = odoo_utils.create_sale_order(decision['partner_name'], decision['lines'])
                    output = f"Created sale order {so['name']}: ${so['amount_total']} - {decision['reason']}"
                    audit_logger.log_action("create_sale_order", "orchestrator", decision['partner_name'], {"amount": so['amount_total'], "source": filepath.name}, "approved", "success")
                elif action == 'update_crm_stage':
                    import odoo_utils
                    result = odoo_utils.update_crm_stage(decision['lead_name'], decision['stage_name'])
                    output = f"Updated CRM: {result['name']} → {result['stage']} - {decision['reason']}"
                    audit_logger.log_action("update_crm_stage", "orchestrator", decision['lead_name'], {"stage": decision['stage_name'], "source": filepath.name}, "approved", "success")
                else:
                    output = f"No action needed: {decision.get('reason', 'N/A')}"
                    audit_logger.log_action("no_action", "orchestrator", filepath.name, {"reason": decision.get('reason', 'N/A')}, "approved", "skipped")
            except (_json.JSONDecodeError, KeyError) as e:
                output = f"Claude response (could not parse as action): {output}"

    except subprocess.TimeoutExpired:
        output = 'Timed out after 120 seconds'
        status = 'failed'
    except Exception as e:
        output = str(e)
        status = 'failed'

    # Log the execution result
    LOGS.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_content = (
        f'---\n'
        f'source: {filepath.name}\n'
        f'status: {status}\n'
        f'executed: {datetime.now().isoformat()}\n'
        f'---\n\n'
        f'## Original Action\n{content}\n\n'
        f'## Result\n{output}\n'
    )
    log_file = LOGS / f'EXEC_{timestamp}_{filepath.stem}.md'
    log_file.write_text(log_content)

    # Move to Done
    DONE.mkdir(exist_ok=True)
    filepath.rename(DONE / filepath.name)
    logging.info(f'{status}: {filepath.name} → Done/')

    return status


def _get_clean_env():
    """Return environment dict with CLAUDECODE removed and nvm bin in PATH."""
    clean_env = {k: v for k, v in os.environ.items() if k != 'CLAUDECODE'}
    nvm_bin = '/home/hamza/.nvm/versions/node/v24.13.1/bin'
    if nvm_bin not in clean_env.get('PATH', ''):
        clean_env['PATH'] = nvm_bin + ':' + clean_env.get('PATH', '')
    return clean_env


def classify_file(filepath):
    """Use Claude CLI to classify a Needs_Action file.

    Returns dict with keys: classification, description, action (if actionable).
    Classification is one of: noise, automated, informational, actionable.
    """
    content = filepath.read_text()
    logging.info(f'Classifying: {filepath.name}')

    prompt = (
        "You are an AI employee assistant. Classify the following inbox item.\n"
        "Respond in this exact JSON format (no markdown, no backticks):\n"
        '{"classification": "noise"|"automated"|"informational"|"actionable", '
        '"description": "one-line summary of the item", '
        '"recommended_action": "what to do (or \'none\')"}\n\n'
        "Classification guide:\n"
        "- noise: spam, false positives, messages that are just numbers or gibberish\n"
        "- automated: service notifications (password resets, PINs, alerts) needing no human response\n"
        "- informational: real messages that are acknowledgments/FYIs needing no response\n"
        "- actionable: messages requiring a follow-up reply or action\n\n"
        f"---\n{content}\n---"
    )

    clean_env = _get_clean_env()

    try:
        result = subprocess.run(
            [CLAUDE_BIN, '--print', '--model', 'haiku', '-p', prompt],
            cwd=str(VAULT), env=clean_env,
            capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL,
        )

        output = result.stdout.strip()
        if result.returncode != 0:
            logging.warning(f'Claude CLI returned {result.returncode} for {filepath.name}')
            return {'classification': 'noise', 'description': 'Claude CLI error', 'recommended_action': 'none'}

        # Strip markdown code fences if present
        clean = output.strip()
        if clean.startswith('```'):
            clean = clean.split('\n', 1)[1] if '\n' in clean else clean[3:]
            clean = clean.rsplit('```', 1)[0].strip()

        return json.loads(clean)

    except subprocess.TimeoutExpired:
        logging.error(f'Timed out classifying {filepath.name}')
        return {'classification': 'noise', 'description': 'Timed out', 'recommended_action': 'none'}
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f'Error classifying {filepath.name}: {e}')
        return {'classification': 'noise', 'description': str(e), 'recommended_action': 'none'}


def create_plan(filepath, classification):
    """Create a plan file in Plans/ for a processed inbox item."""
    PLANS.mkdir(exist_ok=True)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    cat = classification['classification']
    desc = classification.get('description', 'N/A')
    action = classification.get('recommended_action', 'none')

    actionable = cat == 'actionable'
    plan_content = (
        f"---\n"
        f"file: {filepath.name}\n"
        f"classification: {cat}\n"
        f"processed: {now}\n"
        f"---\n\n"
        f"# Plan: {filepath.stem}\n\n"
        f"## Classification: {cat}\n"
        f"{desc}\n\n"
        f"## Recommended Action\n"
        f"{action}\n\n"
        f"## Checklist\n"
        f"- [x] Read and classified\n"
        f"- [{'x' if not actionable else ' '}] No action required\n"
        f"- [{'x' if not actionable else ' '}] Moved to Done/\n"
        f"- [{' ' if not actionable else 'x'}] Moved to Pending_Approval/ for human review\n"
    )

    plan_file = PLANS / f'PLAN_{filepath.stem}.md'
    plan_file.write_text(plan_content)
    return plan_file


def update_dashboard(counts):
    """Regenerate Dashboard.md with current counts."""
    now = datetime.now().strftime('%Y-%m-%d')

    # Count existing files in key directories
    needs_count = len(list(NEEDS_ACTION.glob('*.md'))) if NEEDS_ACTION.exists() else 0
    pending_count = len(list(PENDING_APPROVAL.glob('*.md'))) if PENDING_APPROVAL.exists() else 0
    plans_count = len(list(PLANS.glob('*.md'))) if PLANS.exists() else 0
    done_count = len(list(DONE.glob('*.md'))) if DONE.exists() else 0

    # Read existing activity log if present
    existing_activity = []
    if DASHBOARD.exists():
        in_activity = False
        for line in DASHBOARD.read_text().splitlines():
            if line.startswith('## Recent Activity'):
                in_activity = True
                continue
            if in_activity and line.startswith('- '):
                existing_activity.append(line)
            elif in_activity and line.startswith('##'):
                break

    # Build new activity entry
    total = sum(counts.values())
    parts = ', '.join(f'{v} {k}' for k, v in counts.items() if v > 0)
    new_entry = f'- [{now}] Processed {total} Needs_Action files ({parts})'

    activity_lines = [new_entry] + [l for l in existing_activity if l != new_entry]
    activity_lines = activity_lines[:15]  # Keep last 15 entries

    content = (
        f"# AI Employee Dashboard\n"
        f"Last Updated: {now}\n\n"
        f"## Status\n"
        f"- Pending Actions: {needs_count}\n"
        f"- Pending Approval: {pending_count}\n"
        f"- Active Plans: {plans_count}\n"
        f"- Completed: {done_count}\n\n"
        f"## Active Watchers\n"
        f"- gmail-watcher: online (PM2)\n"
        f"- wa-watcher: online (PM2)\n"
        f"- orchestrator: online (PM2)\n"
        f"- accounting-watcher: online (PM2) — Odoo CRM/Sales/Inventory/Accounting\n\n"
        f"## Inbox Processing Summary ({now})\n"
        f"| Classification | Count | Action Taken |\n"
        f"|---|---|---|\n"
    )
    for cat in ['noise', 'automated', 'informational', 'actionable']:
        c = counts.get(cat, 0)
        action = 'Moved to Pending_Approval/' if cat == 'actionable' and c > 0 else 'Moved to Done/'
        content += f"| {cat} | {c} | {action} |\n"
    content += f"| **Total** | **{total}** | **All processed** |\n\n"
    content += "## Recent Activity\n"
    content += '\n'.join(activity_lines) + '\n'

    DASHBOARD.write_text(content)
    logging.info(f'Dashboard updated: {total} files processed')


def process_needs_action():
    """Scan Needs_Action/, classify each file, create plans, and route accordingly.

    - noise/automated/informational → Done/
    - actionable → Pending_Approval/ (needs human review)

    Returns dict of counts by classification.
    """
    NEEDS_ACTION.mkdir(exist_ok=True)
    DONE.mkdir(exist_ok=True)
    PENDING_APPROVAL.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)

    files = sorted(NEEDS_ACTION.glob('*.md'))
    if not files:
        logging.info('No files in Needs_Action/ to process.')
        return {}

    logging.info(f'Processing {len(files)} files from Needs_Action/')
    counts = {'noise': 0, 'automated': 0, 'informational': 0, 'actionable': 0}

    for filepath in files:
        try:
            classification = classify_file(filepath)
            cat = classification.get('classification', 'noise')
            if cat not in counts:
                cat = 'noise'
            counts[cat] += 1

            # Create plan
            create_plan(filepath, classification)

            # Route the file
            if cat == 'actionable':
                filepath.rename(PENDING_APPROVAL / filepath.name)
                logging.info(f'{filepath.name} → Pending_Approval/ (actionable)')
            else:
                filepath.rename(DONE / filepath.name)
                logging.info(f'{filepath.name} → Done/ ({cat})')

            # Log
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_content = (
                f"---\n"
                f"source: {filepath.name}\n"
                f"classification: {cat}\n"
                f"processed: {datetime.now().isoformat()}\n"
                f"---\n\n"
                f"## Classification\n"
                f"{json.dumps(classification, indent=2)}\n"
            )
            log_file = LOGS / f'CLASSIFY_{timestamp}_{filepath.stem}.md'
            log_file.write_text(log_content)

        except Exception as e:
            logging.error(f'Error processing {filepath.name}: {e}')

    # Update dashboard
    update_dashboard(counts)

    logging.info(f'Done: {json.dumps(counts)}')
    return counts


def generate_linkedin_post():
    """Generate a weekly LinkedIn post based on recent activity and place in Pending_Approval/.

    Reads Done/ and Logs/ to summarize what happened this week, then uses Claude CLI
    to draft a professional LinkedIn post.
    """
    PENDING_APPROVAL.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)

    today = datetime.now()
    date_str = today.strftime('%Y-%m-%d')
    filename = f'LINKEDIN_POST_{date_str}.md'

    # Check if already generated today
    if (PENDING_APPROVAL / filename).exists() or (DONE / filename).exists():
        logging.info(f'LinkedIn post already exists for {date_str}, skipping.')
        return

    # Gather recent activity context
    activity_summary = []

    # Recent logs from this week
    if LOGS.exists():
        for log_file in sorted(LOGS.glob('*.md'), reverse=True)[:20]:
            try:
                content = log_file.read_text()
                activity_summary.append(f"[{log_file.name}]\n{content[:300]}")
            except Exception:
                pass

    # Dashboard for overall stats
    dashboard_text = ''
    if DASHBOARD.exists():
        dashboard_text = DASHBOARD.read_text()

    # Company handbook for tone/priorities
    handbook_path = VAULT / 'Company_Handbook.md'
    handbook_text = ''
    if handbook_path.exists():
        handbook_text = handbook_path.read_text()

    context = '\n\n---\n\n'.join([
        f"## Dashboard\n{dashboard_text}",
        f"## Company Handbook\n{handbook_text}",
        f"## Recent Activity Logs (last 20)\n" + '\n---\n'.join(activity_summary[:10]),
    ])

    prompt = (
        "You are a professional LinkedIn content writer for a small tech business.\n"
        "Based on the following business activity from this week, write a LinkedIn post.\n\n"
        "Requirements:\n"
        "- Professional but conversational tone\n"
        "- Highlight what was accomplished this week\n"
        "- Include a helpful tip relevant to AI automation or small business\n"
        "- End with a call-to-action for potential clients\n"
        "- Include 3-5 relevant hashtags\n"
        "- Keep it under 1300 characters (LinkedIn optimal length)\n"
        "- Output ONLY the post text, no markdown headers or metadata\n\n"
        f"---\n{context}\n---"
    )

    clean_env = _get_clean_env()

    try:
        result = subprocess.run(
            [CLAUDE_BIN, '--print', '--model', 'haiku', '-p', prompt],
            cwd=str(VAULT), env=clean_env,
            capture_output=True, text=True, timeout=120,
            stdin=subprocess.DEVNULL,
        )

        if result.returncode != 0:
            logging.error(f'Claude CLI failed for LinkedIn post: {result.stderr}')
            return

        post_text = result.stdout.strip()

    except subprocess.TimeoutExpired:
        logging.error('Timed out generating LinkedIn post')
        return
    except Exception as e:
        logging.error(f'Error generating LinkedIn post: {e}')
        return

    # Write to Pending_Approval
    post_content = (
        f"---\n"
        f"type: linkedin_post\n"
        f"status: pending_approval\n"
        f"created: {date_str}\n"
        f"publish_date: {date_str}\n"
        f"skill: linkedin-auto-post\n"
        f"---\n\n"
        f"# LinkedIn Post — {today.strftime('%B %d, %Y')}\n\n"
        f"## Post Content\n\n"
        f"---\n\n"
        f"{post_text}\n\n"
        f"---\n\n"
        f"## Checklist\n"
        f"- [x] Post drafted by AI\n"
        f"- [ ] Reviewed by human\n"
        f"- [ ] Copy-pasted to LinkedIn\n"
    )

    post_file = PENDING_APPROVAL / filename
    post_file.write_text(post_content)
    logging.info(f'LinkedIn post generated: {filename} → Pending_Approval/')

    # Log it
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOGS / f'LINKEDIN_{timestamp}.md'
    log_file.write_text(
        f"---\nsource: linkedin-auto-post\ngenerated: {datetime.now().isoformat()}\n---\n\n"
        f"Generated LinkedIn post for {date_str}\nFile: {filename}\n"
    )


def watch_approved():
    """Original loop: watch /Approved and execute actions."""
    APPROVED.mkdir(exist_ok=True)
    logging.info('Orchestrator started, watching /Approved folder...')

    while True:
        for filepath in sorted(APPROVED.glob('*.md')):
            try:
                execute_approved(filepath)
            except Exception as e:
                logging.error(f'Error processing {filepath.name}: {e}')
        time.sleep(10)


def main():
    parser = argparse.ArgumentParser(description='AI Employee Orchestrator')
    parser.add_argument('--process-inbox', action='store_true',
                        help='One-shot: classify Needs_Action/ files and exit')
    parser.add_argument('--generate-linkedin', action='store_true',
                        help='One-shot: generate a weekly LinkedIn post and exit')
    args = parser.parse_args()

    if args.process_inbox:
        process_needs_action()
    elif args.generate_linkedin:
        generate_linkedin_post()
    else:
        watch_approved()


if __name__ == '__main__':
    main()
