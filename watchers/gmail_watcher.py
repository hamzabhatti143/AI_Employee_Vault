from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from base_watcher import BaseWatcher
from config import get_gmail_config
from pathlib import Path
from datetime import datetime
import json, logging, time

logging.basicConfig(level=logging.INFO)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]
WATCHER_DIR = Path(__file__).parent
CLIENT_SECRET = WATCHER_DIR / 'client_secret_1096764676267-8dcb5r2q96s3hlof2rdfttd90h6nhd6b.apps.googleusercontent.com.json'
TOKEN_FILE = WATCHER_DIR / 'gmail_token.json'


def _token_scopes_match(token_path, required_scopes):
    """Check if saved token has all required scopes."""
    try:
        data = json.loads(token_path.read_text())
        saved = set(data.get('scopes', []))
        return set(required_scopes).issubset(saved)
    except Exception:
        return False


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        if not _token_scopes_match(TOKEN_FILE, SCOPES):
            logging.info('Token scopes changed, re-authenticating...')
            TOKEN_FILE.unlink()
        else:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
        except Exception as e:
            logging.error(f'Token refresh failed: {e}')
            creds = None

    if not creds or not creds.valid:
        # In interactive mode, run the OAuth flow; in PM2 just fail clearly
        import sys
        if not sys.stdin.isatty():
            logging.error(
                'Gmail token is missing or expired and cannot re-authenticate in headless mode. '
                'Run manually: cd watchers && .venv/bin/python gmail_watcher.py'
            )
            raise SystemExit(1)
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=8090, open_browser=False)
        TOKEN_FILE.write_text(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


class GmailWatcher(BaseWatcher):
    def __init__(self, vault_path):
        cfg = get_gmail_config()
        self.filters = cfg.get('filters', [
            {'name': 'important-unread', 'query': 'is:unread is:important', 'check_interval': 120}
        ])
        # Use the shortest filter interval as the main loop interval
        min_interval = min(f.get('check_interval', 120) for f in self.filters)
        super().__init__(vault_path, min_interval)
        self.service = get_service()
        self.processed = set()
        self._filter_last_checked = {}

    def check_for_updates(self):
        now = time.time()
        new_messages = []

        for filt in self.filters:
            name = filt['name']
            interval = filt.get('check_interval', 120)
            last = self._filter_last_checked.get(name, 0)

            if now - last < interval:
                continue

            self._filter_last_checked[name] = now
            query = filt['query']

            try:
                results = self.service.users().messages().list(
                    userId='me', q=query
                ).execute()
            except Exception as e:
                self.logger.error(f'Filter "{name}" query failed: {e}')
                # Try refreshing the service on auth errors
                if 'invalid_grant' in str(e).lower() or '401' in str(e):
                    try:
                        self.service = get_service()
                        self.logger.info('Refreshed Gmail service after auth error')
                    except Exception:
                        pass
                continue

            for msg in results.get('messages', []):
                msg_key = (msg['id'], name)
                if msg_key in self.processed:
                    continue
                try:
                    full = self.service.users().messages().get(
                        userId='me', id=msg['id']
                    ).execute()
                    full['_filter_name'] = name
                    new_messages.append(full)
                    self.processed.add(msg_key)
                except Exception as e:
                    self.logger.error(f'Failed to fetch message {msg["id"]}: {e}')

        return new_messages

    def create_action_file(self, msg):
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        filter_name = msg.get('_filter_name', 'unknown')
        content = (
            f'---\n'
            f'type: email\n'
            f'from: {headers.get("From")}\n'
            f'subject: {headers.get("Subject")}\n'
            f'received: {datetime.now().isoformat()}\n'
            f'message_id: {msg["id"]}\n'
            f'filter: {filter_name}\n'
            f'---\n\n'
            f'## Snippet\n{msg.get("snippet", "")}\n'
        )
        filepath = self.needs_action / f'EMAIL_{msg["id"]}.md'
        filepath.write_text(content)
        self.logger.info(f'[{filter_name}] New email: {headers.get("Subject")}')

    def get_notification_text(self, msg):
        headers = {h['name']: h['value'] for h in msg['payload']['headers']}
        title = f'New Email [{msg.get("_filter_name", "")}]'
        body = f'From: {headers.get("From", "?")}\n{headers.get("Subject", "(no subject)")}'
        return title, body


if __name__ == '__main__':
    watcher = GmailWatcher('/mnt/d/ai-employee-vault')
    watcher.run()
