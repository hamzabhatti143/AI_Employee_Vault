"""Audit logger — logs all actions taken by the vault system."""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

VAULT = Path(__file__).parent.parent
LOGS_DIR = VAULT / "Logs"


def log_action(action_type, actor, target, parameters, approval_status, result):
    """Log an action to the daily JSON audit log.

    Args:
        action_type: e.g. 'send_email', 'send_whatsapp', 'create_invoice', 'post_facebook'
        actor: e.g. 'orchestrator', 'mcp_server', 'user'
        target: e.g. email address, contact name, invoice number
        parameters: dict of action parameters
        approval_status: 'approved', 'auto', 'manual'
        result: 'success', 'failed', or error message
    """
    LOGS_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "parameters": parameters,
        "approval_status": approval_status,
        "result": result,
    }

    logs = []
    if log_file.exists():
        try:
            logs = json.loads(log_file.read_text())
        except json.JSONDecodeError:
            logs = []

    logs.append(entry)
    log_file.write_text(json.dumps(logs, indent=2))
    logger.info(f"Logged: {action_type} on {target} → {result}")
