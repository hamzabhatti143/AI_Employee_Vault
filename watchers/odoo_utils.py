"""Odoo XML-RPC utilities for the orchestrator."""
import os
import xmlrpc.client
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

ODOO_URL = os.getenv('ODOO_URL', 'http://localhost:8069')
ODOO_DB = os.getenv('ODOO_DB', 'odoo_main')
ODOO_USER = os.getenv('ODOO_USERNAME', 'admin')
ODOO_PASS = os.getenv('ODOO_PASSWORD', 'admin')


def _connect():
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    if not uid:
        raise RuntimeError('Odoo authentication failed')
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', allow_none=True)
    return uid, models


def create_invoice(partner_name, lines, invoice_type='out_invoice'):
    """Create and post an invoice.

    Args:
        partner_name: Customer/vendor name (must exist in Odoo)
        lines: List of dicts with keys: description, quantity, price_unit
        invoice_type: 'out_invoice' (customer) or 'in_invoice' (vendor bill)

    Returns: dict with invoice id, name, amount_total
    """
    uid, models = _connect()

    # Find partner
    partners = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search_read',
        [[('name', 'ilike', partner_name)]], {'fields': ['id', 'name'], 'limit': 1})
    if not partners:
        raise ValueError(f'Partner not found: {partner_name}')
    partner_id = partners[0]['id']

    # Find income/expense account
    if invoice_type == 'out_invoice':
        acc_type = 'income'
    else:
        acc_type = 'expense'
    accounts = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.account', 'search_read',
        [[('account_type', '=', acc_type)]], {'fields': ['id'], 'limit': 1})
    account_id = accounts[0]['id']

    # Find journal
    journal_type = 'sale' if invoice_type == 'out_invoice' else 'purchase'
    journals = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.journal', 'search_read',
        [[('type', '=', journal_type)]], {'fields': ['id'], 'limit': 1})
    journal_id = journals[0]['id']

    # Build invoice lines
    invoice_lines = []
    for line in lines:
        invoice_lines.append((0, 0, {
            'name': line['description'],
            'quantity': line.get('quantity', 1),
            'price_unit': line['price_unit'],
            'account_id': account_id,
        }))

    inv_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'create', [{
        'move_type': invoice_type,
        'partner_id': partner_id,
        'journal_id': journal_id,
        'invoice_line_ids': invoice_lines,
    }])

    # Post it
    models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'action_post', [[inv_id]])

    inv = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'account.move', 'search_read',
        [[('id', '=', inv_id)]], {'fields': ['name', 'amount_total', 'state']})
    return inv[0]


def create_crm_lead(name, partner_name=None, expected_revenue=0, description='', lead_type='opportunity'):
    """Create a CRM lead or opportunity.

    Returns: dict with lead id, name
    """
    uid, models = _connect()

    vals = {
        'name': name,
        'expected_revenue': expected_revenue,
        'description': description,
        'type': lead_type,
    }

    if partner_name:
        partners = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search_read',
            [[('name', 'ilike', partner_name)]], {'fields': ['id'], 'limit': 1})
        if partners:
            vals['partner_id'] = partners[0]['id']

    lead_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'crm.lead', 'create', [vals])
    lead = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'crm.lead', 'search_read',
        [[('id', '=', lead_id)]], {'fields': ['name', 'stage_id']})
    return lead[0]


def create_sale_order(partner_name, lines):
    """Create and confirm a sales order.

    Args:
        partner_name: Customer name
        lines: List of dicts with keys: product_name, quantity, price_unit

    Returns: dict with order id, name, amount_total
    """
    uid, models = _connect()

    partners = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'res.partner', 'search_read',
        [[('name', 'ilike', partner_name)]], {'fields': ['id'], 'limit': 1})
    if not partners:
        raise ValueError(f'Partner not found: {partner_name}')

    order_lines = []
    for line in lines:
        products = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'product.product', 'search_read',
            [[('name', 'ilike', line['product_name'])]], {'fields': ['id'], 'limit': 1})
        if not products:
            raise ValueError(f'Product not found: {line["product_name"]}')
        order_lines.append((0, 0, {
            'product_id': products[0]['id'],
            'product_uom_qty': line.get('quantity', 1),
            'price_unit': line['price_unit'],
        }))

    so_id = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'sale.order', 'create', [{
        'partner_id': partners[0]['id'],
        'order_line': order_lines,
    }])

    models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'sale.order', 'action_confirm', [[so_id]])

    so = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'sale.order', 'search_read',
        [[('id', '=', so_id)]], {'fields': ['name', 'amount_total', 'state']})
    return so[0]


def update_crm_stage(lead_name, stage_name):
    """Move a CRM lead/opportunity to a different stage.

    Returns: dict with lead id, name, new stage
    """
    uid, models = _connect()

    leads = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'crm.lead', 'search_read',
        [[('name', 'ilike', lead_name)]], {'fields': ['id', 'name'], 'limit': 1})
    if not leads:
        raise ValueError(f'Lead not found: {lead_name}')

    stages = models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'crm.stage', 'search_read',
        [[('name', 'ilike', stage_name)]], {'fields': ['id', 'name'], 'limit': 1})
    if not stages:
        raise ValueError(f'Stage not found: {stage_name}')

    models.execute_kw(ODOO_DB, uid, ODOO_PASS, 'crm.lead', 'write',
        [[leads[0]['id']], {'stage_id': stages[0]['id']}])

    return {'id': leads[0]['id'], 'name': leads[0]['name'], 'stage': stages[0]['name']}
