import subprocess, logging
from config import get_notification_config

logger = logging.getLogger(__name__)


def notify(title, body):
    cfg = get_notification_config()
    if not cfg.get('enabled', True):
        return

    if cfg.get('desktop', {}).get('enabled', True):
        _desktop_notify(title, body)

    tg = cfg.get('telegram', {})
    if tg.get('bot_token') and tg.get('chat_id'):
        _telegram_notify(tg['bot_token'], tg['chat_id'], title, body)


def _desktop_notify(title, body):
    try:
        subprocess.run(
            ['notify-send', '--app-name=Watcher', title, body],
            timeout=5, check=False,
        )
    except FileNotFoundError:
        logger.debug('notify-send not available')
    except Exception as e:
        logger.warning(f'Desktop notification failed: {e}')


def _telegram_notify(bot_token, chat_id, title, body):
    # Stubbed for future use
    try:
        import requests
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        requests.post(url, json={
            'chat_id': chat_id,
            'text': f'*{title}*\n{body}',
            'parse_mode': 'Markdown',
        }, timeout=10)
    except Exception as e:
        logger.warning(f'Telegram notification failed: {e}')
