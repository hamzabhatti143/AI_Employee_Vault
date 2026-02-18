import json
import time
from pathlib import Path

VAULT = Path(__file__).parent.parent
OUTBOX = VAULT / 'wa_outbox'


def send_message(contact: str, message: str) -> Path:
    """Queue a WhatsApp message for sending via the watcher process.

    Writes a JSON request file to wa_outbox/ that the watcher picks up.
    Returns the path of the created request file.
    """
    OUTBOX.mkdir(exist_ok=True)
    request = {"contact": contact, "message": message}
    filename = f"SEND_{int(time.time() * 1000)}.json"
    filepath = OUTBOX / filename
    filepath.write_text(json.dumps(request))
    return filepath
