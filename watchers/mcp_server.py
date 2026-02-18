"""MCP server exposing AI Employee Vault tools (Gmail, WhatsApp, Odoo)."""

import sys
from pathlib import Path

# Ensure watchers directory is on the import path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

import gmail_utils
import whatsapp_utils
import odoo_utils
import social_utils
import twitter_utils
import audit_logger

mcp = FastMCP("employee-tools")


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Compose and send a new email via Gmail.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body text
    """
    result = gmail_utils.send_email(to, subject, body)
    audit_logger.log_action("send_email", "mcp_server", to, {"subject": subject}, "manual", "success")
    return f"Email sent to {to}, id={result['id']}"


@mcp.tool()
def send_bulk_email(recipients: str, subject: str, body: str) -> str:
    """Send the same email to multiple recipients.

    Args:
        recipients: Comma-separated list of email addresses (e.g. "a@x.com,b@x.com")
        subject: Email subject line
        body: Email body text
    """
    recipient_list = [e.strip() for e in recipients.split(',') if e.strip()]
    result = gmail_utils.send_bulk_email(recipient_list, subject, body)
    audit_logger.log_action(
        "send_bulk_email", "mcp_server", f"{len(recipient_list)} recipients",
        {"subject": subject, "sent": len(result["sent"]), "failed": len(result["failed"])},
        "manual", "success"
    )
    summary = f"Bulk email: {len(result['sent'])} sent, {len(result['failed'])} failed out of {result['total']}"
    if result['failed']:
        summary += "\nFailed: " + ", ".join(f["email"] for f in result["failed"])
    return summary


@mcp.tool()
def reply_to_email(message_id: str, body: str) -> str:
    """Reply in-thread to an existing Gmail message.

    Args:
        message_id: The Gmail message ID to reply to
        body: Reply body text
    """
    result = gmail_utils.reply_to_email(message_id, body)
    audit_logger.log_action("reply_email", "mcp_server", message_id, {}, "manual", "success")
    return f"Reply sent, thread={result.get('threadId')}, id={result['id']}"


@mcp.tool()
def send_whatsapp(contact: str, message: str) -> str:
    """Send a WhatsApp message via the outbox queue.

    The wa-watcher process picks up queued messages and delivers them.

    Args:
        contact: Contact name as it appears in WhatsApp
        message: Message text to send
    """
    filepath = whatsapp_utils.send_message(contact, message)
    audit_logger.log_action("send_whatsapp", "mcp_server", contact, {"message": message[:100]}, "manual", "success")
    return f"WhatsApp message queued: {filepath.name}"


@mcp.tool()
def create_invoice(partner_name: str, lines: list, invoice_type: str = "out_invoice") -> str:
    """Create and post an invoice in Odoo.

    Args:
        partner_name: Customer or vendor name (must exist in Odoo)
        lines: List of line items, each a dict with 'description', 'quantity', 'price_unit'
        invoice_type: 'out_invoice' for customer invoice, 'in_invoice' for vendor bill
    """
    result = odoo_utils.create_invoice(partner_name, lines, invoice_type)
    audit_logger.log_action("create_invoice", "mcp_server", partner_name, {"type": invoice_type, "amount": result['amount_total']}, "manual", "success")
    return f"Invoice {result['name']} created: ${result['amount_total']} ({result['state']})"


@mcp.tool()
def create_crm_lead(name: str, partner_name: str = "", expected_revenue: float = 0, description: str = "", lead_type: str = "opportunity") -> str:
    """Create a CRM lead or opportunity in Odoo.

    Args:
        name: Lead/opportunity title
        partner_name: Associated partner name (optional)
        expected_revenue: Expected revenue amount
        description: Lead description/notes
        lead_type: 'opportunity' or 'lead'
    """
    result = odoo_utils.create_crm_lead(name, partner_name or None, expected_revenue, description, lead_type)
    stage = result['stage_id'][1] if result['stage_id'] else 'N/A'
    audit_logger.log_action("create_crm_lead", "mcp_server", name, {"partner": partner_name, "revenue": expected_revenue}, "manual", "success")
    return f"CRM {lead_type} created: {result['name']} (stage: {stage})"


@mcp.tool()
def create_sale_order(partner_name: str, lines: list) -> str:
    """Create and confirm a sales order in Odoo.

    Args:
        partner_name: Customer name (must exist in Odoo)
        lines: List of line items, each a dict with 'product_name', 'quantity', 'price_unit'
    """
    result = odoo_utils.create_sale_order(partner_name, lines)
    audit_logger.log_action("create_sale_order", "mcp_server", partner_name, {"amount": result['amount_total']}, "manual", "success")
    return f"Sale order {result['name']} created: ${result['amount_total']} ({result['state']})"


@mcp.tool()
def update_crm_stage(lead_name: str, stage_name: str) -> str:
    """Move a CRM lead/opportunity to a different pipeline stage in Odoo.

    Args:
        lead_name: Name of the lead/opportunity
        stage_name: Target stage name (e.g. 'New', 'Qualified', 'Proposition', 'Won')
    """
    result = odoo_utils.update_crm_stage(lead_name, stage_name)
    audit_logger.log_action("update_crm_stage", "mcp_server", lead_name, {"stage": stage_name}, "manual", "success")
    return f"CRM updated: {result['name']} → {result['stage']}"


@mcp.tool()
def odoo_search(model: str, domain: list = None, fields: list = None, limit: int = 10) -> str:
    """Search and read records from any Odoo model.

    Args:
        model: Odoo model name (e.g. 'res.partner', 'account.move', 'crm.lead', 'sale.order', 'product.product')
        domain: Search filter as list of tuples, e.g. [['state', '=', 'posted']]
        fields: List of field names to return, e.g. ['name', 'amount_total']
        limit: Max number of records to return
    """
    import json
    uid, models = odoo_utils._connect()
    results = models.execute_kw(
        odoo_utils.ODOO_DB, uid, odoo_utils.ODOO_PASS, model, 'search_read',
        [domain or []], {'fields': fields or [], 'limit': limit}
    )
    return json.dumps(results, indent=2, default=str)


@mcp.tool()
def post_facebook(message: str, image_url: str = None) -> str:
    """Post to the Facebook Page.

    Args:
        message: Post text content.
        image_url: Optional publicly-accessible image URL to attach as a photo.
    """
    result = social_utils.post_to_facebook(message, image_url)
    audit_logger.log_action("post_facebook", "mcp_server", "facebook_page", {"message": message[:100]}, "manual", "success")
    return f"Facebook post created: id={result.get('id')}"


@mcp.tool()
def post_instagram(image_url: str, caption: str) -> str:
    """Post a photo to Instagram Business account.

    Args:
        image_url: Publicly-accessible image URL (JPEG recommended, < 8MB).
        caption: Post caption text (max 2200 chars).
    """
    result = social_utils.post_to_instagram(image_url, caption)
    audit_logger.log_action("post_instagram", "mcp_server", "instagram", {"caption": caption[:100]}, "manual", "success")
    return f"Instagram post published: id={result.get('id')}"


@mcp.tool()
def draft_tweet(text: str) -> str:
    """Draft a tweet and save it to Needs_Action/ for user approval.

    The user will review and post it manually.

    Args:
        text: Tweet text (max 280 chars).
    """
    import time
    from datetime import datetime

    vault = Path(__file__).parent.parent
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(exist_ok=True)

    filename = f"TWEET_DRAFT_{int(time.time())}.md"
    char_count = len(text)
    content = (
        f"---\n"
        f"type: tweet_draft\n"
        f"date: {datetime.now().isoformat()}\n"
        f"chars: {char_count}/280\n"
        f"---\n\n"
        f"## Tweet Draft\n\n"
        f"{text}\n\n"
        f"---\n"
        f"**To post:** Copy the text above and paste it at https://x.com/compose/post\n"
    )
    path = needs_action / filename
    path.write_text(content)
    return f"Tweet draft saved: {filename} ({char_count}/280 chars)"


@mcp.tool()
def draft_linkedin(text: str) -> str:
    """Draft a LinkedIn post and save it to Needs_Action/ for user approval.

    The user will review and post it manually.

    Args:
        text: LinkedIn post text.
    """
    import time
    from datetime import datetime

    vault = Path(__file__).parent.parent
    needs_action = vault / "Needs_Action"
    needs_action.mkdir(exist_ok=True)

    filename = f"LINKEDIN_DRAFT_{int(time.time())}.md"
    char_count = len(text)
    content = (
        f"---\n"
        f"type: linkedin_draft\n"
        f"date: {datetime.now().isoformat()}\n"
        f"chars: {char_count}/3000\n"
        f"---\n\n"
        f"## LinkedIn Post Draft\n\n"
        f"{text}\n\n"
        f"---\n"
        f"**To post:** Copy the text above and paste it at https://www.linkedin.com/feed/?shareActive=true\n"
    )
    path = needs_action / filename
    path.write_text(content)
    return f"LinkedIn draft saved: {filename} ({char_count}/3000 chars)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
