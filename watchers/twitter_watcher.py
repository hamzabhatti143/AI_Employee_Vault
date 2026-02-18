"""Twitter watcher — polls mentions and creates Needs_Action files."""

import logging
import time
from datetime import datetime
from pathlib import Path

from base_watcher import BaseWatcher
from twitter_utils import get_mentions

logging.basicConfig(level=logging.INFO)

VAULT = Path(__file__).parent.parent


class TwitterWatcher(BaseWatcher):
    def __init__(self):
        super().__init__(vault_path=VAULT, check_interval=1800)  # 30 min
        self.seen_ids = set()
        # Load already-existing action files to avoid duplicates on restart
        for f in self.needs_action.glob("TWITTER_*.md"):
            self.seen_ids.add(f.stem)

    def check_for_updates(self):
        mentions = get_mentions(count=10)
        new_mentions = []
        for m in mentions:
            key = f"TWITTER_{m['id']}"
            if key not in self.seen_ids:
                self.seen_ids.add(key)
                new_mentions.append(m)
        return new_mentions

    def create_action_file(self, item):
        filename = f"TWITTER_{item['id']}.md"
        content = (
            f"---\n"
            f"type: twitter_mention\n"
            f"tweet_id: {item['id']}\n"
            f"author: {item['author']}\n"
            f"date: {item['created_at']}\n"
            f"received: {datetime.now().isoformat()}\n"
            f"---\n\n"
            f"## Twitter Mention from {item['author']}\n\n"
            f"{item['text']}\n"
        )
        path = self.needs_action / filename
        path.write_text(content)
        self.logger.info(f"Saved mention: {filename}")

    def get_notification_text(self, item):
        return (
            f"Twitter: {item['author']}",
            item["text"][:100],
        )


if __name__ == "__main__":
    TwitterWatcher().run()
