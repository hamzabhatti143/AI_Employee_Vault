from playwright.sync_api import sync_playwright
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from config import get_whatsapp_config
from notifier import notify
import json, re, shutil, threading, time, signal, logging

logging.basicConfig(level=logging.INFO)

WATCHER_DIR = Path(__file__).parent
VAULT = WATCHER_DIR.parent
# Store session on Linux filesystem for reliable persistence
SESSION = Path.home() / '.whatsapp_session'
QR_SCREENSHOT = VAULT / 'whatsapp_qr.png'

QR_PAGE = '''<!DOCTYPE html><html><head><title>WhatsApp QR</title>
<style>body{display:flex;justify-content:center;align-items:center;height:100vh;background:#111;margin:0}
img{max-width:90vw;max-height:90vh}</style></head>
<body><img src="/qr.png" id="qr"><script>
setInterval(()=>{document.getElementById("qr").src="/qr.png?t="+Date.now()},3000);
</script></body></html>'''


class QRHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path.startswith('/index'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(QR_PAGE.encode())
        elif self.path.startswith('/qr.png'):
            try:
                data = QR_SCREENSHOT.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


def serve_qr():
    server = HTTPServer(('0.0.0.0', 8095), QRHandler)
    server.serve_forever()


def _check_message(text_lower, contact_name, cfg):
    """Check if a message matches keywords based on config rules.

    Returns list of matched keywords, or empty list if no match.
    Contact-specific rules override defaults when the contact matches.
    """
    # Check contact-specific rules first
    for rule in cfg.get('contact_rules', []):
        if rule.get('contact', '').lower() in contact_name.lower():
            keywords = rule.get('keywords', [])
            return [kw for kw in keywords if kw in text_lower]

    # Fall back to default keywords
    keywords = cfg.get('default_keywords', [])
    return [kw for kw in keywords if kw in text_lower]


OUTBOX = VAULT / 'wa_outbox'
OUTBOX_SENT = OUTBOX / 'sent'
OUTBOX_FAILED = OUTBOX / 'failed'


def _is_phone_number(contact):
    """Check if contact is a phone number (digits, +, spaces, dashes)."""
    cleaned = re.sub(r'[\s\-\(\)]', '', contact)
    return bool(re.match(r'^\+?\d{7,15}$', cleaned))


def _normalize_phone(contact):
    """Strip non-digit chars except leading +."""
    cleaned = re.sub(r'[\s\-\(\)]', '', contact)
    return cleaned


def _process_outbox(page):
    """Process pending send requests from wa_outbox/."""
    if not OUTBOX.exists():
        return
    for filepath in sorted(OUTBOX.glob('SEND_*.json')):
        try:
            request = json.loads(filepath.read_text(encoding='utf-8-sig'))
            contact = request['contact']
            message = request['message']
            logging.info(f'Sending message to {contact}...')

            if _is_phone_number(contact):
                # Use direct URL for phone numbers (works for unsaved contacts)
                phone = _normalize_phone(contact)
                phone_url = phone.lstrip('+')
                page.goto(f'https://web.whatsapp.com/send?phone={phone_url}')

                # Wait for compose box (WhatsApp auto-opens the chat)
                page.wait_for_selector('div[role="textbox"][aria-label^="Type to"]', timeout=30000)
                time.sleep(1)
            else:
                # Use search box for saved contact names
                search = page.locator('div[role="textbox"][aria-label="Search input textbox"]')
                search.click(force=True)
                time.sleep(0.5)
                search.fill(contact)
                time.sleep(3)

                # Click the first visible search result (top span[title])
                page.locator('span[title]').first.click()
                time.sleep(2)

            # Type message in compose box and send
            compose = page.locator('div[role="textbox"][aria-label^="Type to"]')
            compose.click(force=True)
            time.sleep(0.5)
            compose.fill(message)
            page.keyboard.press('Enter')
            time.sleep(2)

            # Return to chat list
            page.keyboard.press('Escape')
            time.sleep(1)

            # Move to sent/
            OUTBOX_SENT.mkdir(parents=True, exist_ok=True)
            result_data = {**request, 'status': 'sent', 'sent_at': datetime.now().isoformat()}
            dest = OUTBOX_SENT / filepath.name
            dest.write_text(json.dumps(result_data))
            filepath.unlink()
            logging.info(f'Message sent to {contact}, moved to sent/')

        except Exception as e:
            logging.error(f'Failed to send {filepath.name}: {e}')
            OUTBOX_FAILED.mkdir(parents=True, exist_ok=True)
            try:
                request = json.loads(filepath.read_text(encoding='utf-8-sig'))
            except Exception:
                request = {}
            result_data = {**request, 'status': 'failed', 'error': str(e), 'failed_at': datetime.now().isoformat()}
            dest = OUTBOX_FAILED / filepath.name
            dest.write_text(json.dumps(result_data))
            filepath.unlink()
            # Press Escape to reset UI state after failure
            try:
                page.keyboard.press('Escape')
            except Exception:
                pass


def watch_whatsapp():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION), headless=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        # Graceful shutdown: close browser properly so session is saved
        def shutdown(sig, frame):
            logging.info('Shutting down, saving session...')
            browser.close()
            logging.info('Session saved. Exiting.')
            exit(0)
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        page = browser.pages[0]
        page.goto('https://web.whatsapp.com')

        logging.info('Waiting for WhatsApp Web to load...')
        try:
            page.wait_for_selector('[aria-label="Chat list"]', timeout=60000)
            logging.info('WhatsApp already authenticated from saved session!')
        except Exception:
            logging.info('QR code required. Starting live QR server on http://localhost:8095')

            qr_thread = threading.Thread(target=serve_qr, daemon=True)
            qr_thread.start()

            # Wait for any canvas (QR code) to appear
            page.wait_for_selector('canvas', timeout=30000)
            time.sleep(2)

            for attempt in range(30):
                page.screenshot(path=str(QR_SCREENSHOT))
                if attempt == 0:
                    logging.info('Open http://localhost:8095 in your browser and scan the QR with your phone!')
                try:
                    page.wait_for_selector('[aria-label="Chat list"]', timeout=10000)
                    break
                except Exception:
                    pass
            else:
                raise TimeoutError('QR scan not completed within 5 minutes')

            logging.info('WhatsApp connected after QR scan!')
            QR_SCREENSHOT.unlink(missing_ok=True)

        processed = set()
        logging.info('WhatsApp watcher started, monitoring all unread messages...')

        while True:
            try:
                _process_outbox(page)

                cfg = get_whatsapp_config()
                check_interval = cfg.get('check_interval', 30)

                unread = page.query_selector_all('[aria-label*="unread"]')
                for chat in unread:
                    text = chat.inner_text()
                    text_lower = text.lower()
                    chat_id = hash(text[:100])
                    if chat_id in processed:
                        continue

                    # Extract contact name (first line of chat element text)
                    contact_name = text.split('\n')[0] if text else ''
                    found_kws = _check_message(text_lower, contact_name, cfg)

                    # Save ALL unread messages, flag keyword matches as urgent
                    is_urgent = len(found_kws) > 0
                    md = (
                        f'---\n'
                        f'type: whatsapp\n'
                        f'contact: {contact_name}\n'
                        f'detected: {datetime.now().isoformat()}\n'
                        f'urgent: {str(is_urgent).lower()}\n'
                    )
                    if found_kws:
                        md += f'keywords_found: {", ".join(found_kws)}\n'
                    md += (
                        f'---\n\n'
                        f'## Message\n{text[:500]}\n'
                    )
                    filepath = VAULT / 'Needs_Action' / f'WHATSAPP_{int(time.time())}.md'
                    filepath.write_text(md)

                    if is_urgent:
                        logging.info(f'Urgent WhatsApp from {contact_name} (keywords: {found_kws})')
                        notify(
                            'WhatsApp Alert',
                            f'From: {contact_name}\nKeywords: {", ".join(found_kws)}'
                        )
                    else:
                        logging.info(f'WhatsApp from {contact_name} saved')

                    processed.add(chat_id)
            except Exception as e:
                logging.error(f'WA error: {e}')
            time.sleep(check_interval)


if __name__ == '__main__':
    watch_whatsapp()
