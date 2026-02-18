import xmlrpc.client, time, json
from pathlib import Path
from datetime import datetime

VAULT = Path('/mnt/d/ai-employee-vault')
ODOO_URL = 'http://localhost:8069'
DB = 'odoo_main'
USER = 'admin'
PASSWORD = 'admin'

def get_connection():
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common', allow_none=True)
    uid = common.authenticate(DB, USER, PASSWORD, {})
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object', allow_none=True)
    return uid, models

def get_recent_transactions(uid, models):
    return models.execute_kw(DB, uid, PASSWORD, 'account.move', 'search_read',
        [[['state', '=', 'posted']]], {'limit': 20, 'fields': ['name', 'amount_total', 'partner_id', 'invoice_date', 'payment_state', 'move_type']})

def get_crm_leads(uid, models):
    return models.execute_kw(DB, uid, PASSWORD, 'crm.lead', 'search_read',
        [[]], {'limit': 20, 'fields': ['name', 'partner_id', 'expected_revenue', 'stage_id', 'type', 'probability', 'create_date'],
               'order': 'create_date desc'})

def get_sales_orders(uid, models):
    return models.execute_kw(DB, uid, PASSWORD, 'sale.order', 'search_read',
        [[]], {'limit': 20, 'fields': ['name', 'partner_id', 'amount_total', 'state', 'date_order'],
               'order': 'date_order desc'})

def get_inventory(uid, models):
    return models.execute_kw(DB, uid, PASSWORD, 'product.product', 'search_read',
        [[['type', '=', 'product']]], {'fields': ['name', 'default_code', 'qty_available', 'list_price']})

def get_stock_moves(uid, models):
    return models.execute_kw(DB, uid, PASSWORD, 'stock.move', 'search_read',
        [[['state', '=', 'done']]], {'limit': 20, 'fields': ['product_id', 'quantity', 'date', 'origin', 'location_dest_id'],
                                       'order': 'date desc'})

def write_accounting(txns):
    content = f'---\ntype: accounting_update\ndate: {datetime.now().isoformat()}\n---\n'
    if not txns:
        content += '\nNo posted transactions yet.\n'
    for t in txns:
        partner = t['partner_id'][1] if t['partner_id'] else 'N/A'
        content += f'- {t["name"]}: ${t["amount_total"]} from {partner} ({t["payment_state"]})\n'
    (VAULT / 'Accounting' / 'Current_Month.md').write_text(content)

def write_crm(leads):
    content = f'---\ntype: crm_update\ndate: {datetime.now().isoformat()}\n---\n'
    opportunities = [l for l in leads if l['type'] == 'opportunity']
    raw_leads = [l for l in leads if l['type'] == 'lead']

    content += f'\n## Opportunities ({len(opportunities)})\n'
    for l in opportunities:
        partner = l['partner_id'][1] if l['partner_id'] else 'N/A'
        stage = l['stage_id'][1] if l['stage_id'] else 'N/A'
        content += f'- **{l["name"]}** | {partner} | ${l["expected_revenue"]} | {stage} | {l["probability"]}%\n'

    content += f'\n## Leads ({len(raw_leads)})\n'
    for l in raw_leads:
        content += f'- **{l["name"]}** | ${l["expected_revenue"]}\n'

    (VAULT / 'CRM' / 'Pipeline.md').write_text(content)

def write_sales(orders):
    content = f'---\ntype: sales_update\ndate: {datetime.now().isoformat()}\n---\n'
    state_labels = {'draft': 'Quotation', 'sent': 'Sent', 'sale': 'Confirmed', 'done': 'Done', 'cancel': 'Cancelled'}
    for o in orders:
        partner = o['partner_id'][1] if o['partner_id'] else 'N/A'
        state = state_labels.get(o['state'], o['state'])
        content += f'- **{o["name"]}** | {partner} | ${o["amount_total"]} | {state}\n'
    (VAULT / 'Sales' / 'Orders.md').write_text(content)

def write_inventory(products, moves):
    content = f'---\ntype: inventory_update\ndate: {datetime.now().isoformat()}\n---\n'
    content += '\n## Stock Levels\n'
    for p in products:
        code = p['default_code'] or ''
        content += f'- **{p["name"]}** [{code}]: {p["qty_available"]} units (${p["list_price"]} each)\n'

    content += f'\n## Recent Stock Moves ({len(moves)})\n'
    for m in moves:
        product = m['product_id'][1] if m['product_id'] else '?'
        dest = m['location_dest_id'][1] if m['location_dest_id'] else '?'
        content += f'- {m["date"]}: {product} x{m["quantity"]} → {dest}'
        if m['origin']:
            content += f' (from {m["origin"]})'
        content += '\n'
    (VAULT / 'Inventory' / 'Stock.md').write_text(content)

# Ensure directories exist
for d in ['Accounting', 'CRM', 'Sales', 'Inventory']:
    (VAULT / d).mkdir(exist_ok=True)

while True:
    try:
        uid, models = get_connection()

        txns = get_recent_transactions(uid, models)
        write_accounting(txns)
        print(f'[{datetime.now()}] Accounting: {len(txns)} transactions')

        leads = get_crm_leads(uid, models)
        write_crm(leads)
        print(f'[{datetime.now()}] CRM: {len(leads)} leads/opportunities')

        orders = get_sales_orders(uid, models)
        write_sales(orders)
        print(f'[{datetime.now()}] Sales: {len(orders)} orders')

        products = get_inventory(uid, models)
        moves = get_stock_moves(uid, models)
        write_inventory(products, moves)
        print(f'[{datetime.now()}] Inventory: {len(products)} products, {len(moves)} moves')

    except Exception as e:
        print(f'Error: {e}')
    time.sleep(3600)
