"""Social watcher — posts scheduled social media content from Plans/social/."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from base_watcher import BaseWatcher
from social_utils import post_to_facebook, post_to_instagram
from audit_logger import log_action
from notifier import notify

logging.basicConfig(level=logging.INFO)

VAULT = Path(__file__).parent.parent


def _parse_post_file(path):
    """Parse a .md file with YAML-style frontmatter into metadata + body."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta[key.strip()] = val.strip()

    body = parts[2].strip()
    meta["body"] = body
    meta["file_path"] = path
    return meta


class SocialWatcher(BaseWatcher):
    def __init__(self):
        super().__init__(vault_path=VAULT, check_interval=60)
        self.social_dir = VAULT / "Plans" / "social"
        self.done_dir = VAULT / "Done"
        self.done_dir.mkdir(exist_ok=True)

    def check_for_updates(self):
        """Return posts whose scheduled time has passed."""
        if not self.social_dir.exists():
            return []

        ready = []
        now = datetime.now()

        for f in sorted(self.social_dir.glob("*.md")):
            post = _parse_post_file(f)
            if not post:
                self.logger.warning(f"Skipping unparseable file: {f.name}")
                continue

            if post.get("type") != "social_post":
                continue

            scheduled_str = post.get("scheduled")
            if not scheduled_str:
                self.logger.warning(f"No 'scheduled' in {f.name}, skipping")
                continue

            try:
                scheduled_dt = datetime.fromisoformat(scheduled_str)
            except ValueError:
                self.logger.warning(f"Bad date in {f.name}: {scheduled_str}")
                continue

            if scheduled_dt <= now:
                ready.append(post)

        return ready

    def create_action_file(self, item):
        """Post to the platform and move file to Done/."""
        platform = item.get("platform", "").lower()
        body = item.get("body", "")
        image_url = item.get("image_url")
        file_path = item["file_path"]

        try:
            if platform == "facebook":
                result = post_to_facebook(body, image_url or None)
                post_id = result.get("id", "unknown")
            elif platform == "instagram":
                if not image_url:
                    raise ValueError("Instagram posts require an image_url")
                result = post_to_instagram(image_url, body)
                post_id = result.get("id", "unknown")
            else:
                self.logger.error(f"Unknown platform '{platform}' in {file_path.name}")
                return

            # Log success
            log_action(
                action_type=f"post_{platform}",
                actor="social_watcher",
                target=platform,
                parameters={"file": file_path.name, "post_id": post_id},
                approval_status="auto",
                result="success",
            )

            # Move to Done/
            dest = self.done_dir / file_path.name
            shutil.move(str(file_path), str(dest))
            self.logger.info(f"Posted to {platform} (id={post_id}), moved {file_path.name} to Done/")

        except Exception as e:
            self.logger.error(f"Failed to post {file_path.name} to {platform}: {e}")
            log_action(
                action_type=f"post_{platform}",
                actor="social_watcher",
                target=platform,
                parameters={"file": file_path.name},
                approval_status="auto",
                result=f"failed: {e}",
            )
            notify(f"Social post failed", f"{file_path.name}: {e}")

    def get_notification_text(self, item):
        platform = item.get("platform", "social")
        return (f"Posted to {platform}", item.get("body", "")[:100])


if __name__ == "__main__":
    SocialWatcher().run()
