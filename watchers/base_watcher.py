import time, logging
from pathlib import Path
from abc import ABC, abstractmethod
from notifier import notify

class BaseWatcher(ABC):
    def __init__(self, vault_path, check_interval=60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def check_for_updates(self): pass

    @abstractmethod
    def create_action_file(self, item): pass

    def get_notification_text(self, item):
        """Override to return (title, body) tuple for desktop notifications."""
        return None

    def run(self):
        self.logger.info(f'Starting {self.__class__.__name__}')
        while True:
            try:
                for item in self.check_for_updates():
                    self.create_action_file(item)
                    notif = self.get_notification_text(item)
                    if notif:
                        title, body = notif
                        notify(title, body)
            except Exception as e:
                self.logger.error(f'Error: {e}')
            time.sleep(self.check_interval)
