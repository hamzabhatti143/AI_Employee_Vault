import json, time, logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / 'config.json'

_cache = None
_cache_time = 0
_CACHE_TTL = 30  # seconds

DEFAULTS = {
    'notifications': {
        'enabled': True,
        'desktop': {'enabled': True},
        'telegram': {'bot_token': '', 'chat_id': ''},
    },
    'gmail': {
        'filters': [
            {'name': 'important-unread', 'query': 'is:unread is:important', 'check_interval': 120}
        ],
    },
    'whatsapp': {
        'check_interval': 30,
        'default_keywords': ['urgent', 'asap', 'invoice', 'payment', 'help', 'price'],
        'contact_rules': [],
    },
    'social': {
        'facebook': {'max_message_length': 63206},
        'instagram': {'max_caption_length': 2200},
    },
    'twitter': {
        'check_interval': 1800,
        'max_tweet_length': 280,
    },
}


def load_config(force=False):
    global _cache, _cache_time
    now = time.time()
    if not force and _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache
    try:
        raw = CONFIG_PATH.read_text()
        _cache = json.loads(raw)
        _cache_time = now
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f'Config load failed ({e}), using defaults')
        _cache = DEFAULTS.copy()
        _cache_time = now
    return _cache


def get_notification_config():
    cfg = load_config()
    return cfg.get('notifications', DEFAULTS['notifications'])


def get_gmail_config():
    cfg = load_config()
    return cfg.get('gmail', DEFAULTS['gmail'])


def get_whatsapp_config():
    cfg = load_config()
    return cfg.get('whatsapp', DEFAULTS['whatsapp'])


def get_social_config():
    cfg = load_config()
    return cfg.get('social', DEFAULTS['social'])


def get_twitter_config():
    cfg = load_config()
    return cfg.get('twitter', DEFAULTS['twitter'])
