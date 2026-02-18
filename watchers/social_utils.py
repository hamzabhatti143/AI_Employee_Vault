"""Utilities for posting to Facebook Pages and Instagram Business accounts via Meta Graph API."""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from watchers directory
load_dotenv(Path(__file__).parent / ".env")

GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v21.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _validate_config():
    """Check that required env vars are set. Raises ValueError if not."""
    required = ["FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError(f"Missing Meta API env vars: {', '.join(missing)}. See SETUP_META_API.md.")


def _check_token_expiry():
    """Log a warning if the token is nearing expiration."""
    expiry = os.getenv("FACEBOOK_TOKEN_EXPIRY")
    if not expiry:
        logger.warning("FACEBOOK_TOKEN_EXPIRY not set — cannot check token freshness")
        return
    try:
        exp_dt = datetime.fromisoformat(expiry).replace(tzinfo=timezone.utc)
        days_left = (exp_dt - datetime.now(timezone.utc)).days
        if days_left < 7:
            logger.warning(f"Meta Page Access Token expires in {days_left} days! Run refresh_access_token().")
    except ValueError:
        logger.warning(f"Invalid FACEBOOK_TOKEN_EXPIRY format: {expiry}")


def _headers():
    return {"Authorization": f"Bearer {os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')}"}


def post_to_facebook(message: str, image_url: str | None = None) -> dict:
    """Post to a Facebook Page.

    Args:
        message: Post text content.
        image_url: Optional publicly-accessible image URL to attach.

    Returns:
        Dict with 'id' of the created post.
    """
    _validate_config()
    _check_token_expiry()

    page_id = os.getenv("FACEBOOK_PAGE_ID")

    if image_url:
        url = f"{GRAPH_BASE}/{page_id}/photos"
        payload = {"caption": message, "url": image_url}
    else:
        url = f"{GRAPH_BASE}/{page_id}/feed"
        payload = {"message": message}

    resp = requests.post(url, headers=_headers(), data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Facebook post created: {data.get('id')}")
    return data


def post_to_instagram(image_url: str, caption: str) -> dict:
    """Post a photo to Instagram Business account (two-step container flow).

    Args:
        image_url: Publicly-accessible image URL (JPEG recommended, must be < 8MB).
        caption: Post caption text (max 2200 chars).

    Returns:
        Dict with 'id' of the published post.
    """
    _validate_config()
    _check_token_expiry()

    ig_user_id = os.getenv("INSTAGRAM_USER_ID")
    if not ig_user_id:
        raise ValueError("INSTAGRAM_USER_ID not set. See SETUP_META_API.md.")

    # Step 1: Create media container
    container_url = f"{GRAPH_BASE}/{ig_user_id}/media"
    container_payload = {"image_url": image_url, "caption": caption}
    resp = requests.post(container_url, headers=_headers(), data=container_payload, timeout=30)
    resp.raise_for_status()
    container_id = resp.json()["id"]
    logger.info(f"Instagram container created: {container_id}")

    # Step 2: Wait for media to finish processing
    import time
    status_url = f"{GRAPH_BASE}/{container_id}"
    for attempt in range(10):
        time.sleep(5)
        status_resp = requests.get(status_url, headers=_headers(), params={"fields": "status_code"}, timeout=15)
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        logger.info(f"Instagram media processing (attempt {attempt+1}): {status_code}")
    else:
        raise RuntimeError(f"Instagram media not ready after 50s. Container: {container_id}")

    # Step 3: Publish the container
    publish_url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    publish_payload = {"creation_id": container_id}
    resp = requests.post(publish_url, headers=_headers(), data=publish_payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Instagram post published: {data.get('id')}")
    return data


def refresh_access_token() -> dict:
    """Exchange current long-lived token for a new 60-day long-lived token.

    Returns:
        Dict with new 'access_token' and 'expires_in'.
        Remember to update .env with the new token and expiry date.
    """
    _validate_config()
    app_id = os.getenv("META_APP_ID")
    app_secret = os.getenv("META_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("META_APP_ID and META_APP_SECRET required for token refresh.")

    current_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": current_token,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info(f"Token refreshed, expires_in={data.get('expires_in')}s")
    return data


# --- CLI for quick testing ---
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python social_utils.py facebook 'message' [image_url]")
        print("  python social_utils.py instagram 'image_url' 'caption'")
        print("  python social_utils.py refresh-token")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "facebook":
        msg = sys.argv[2]
        img = sys.argv[3] if len(sys.argv) > 3 else None
        result = post_to_facebook(msg, img)
        print(f"Posted to Facebook: {result}")

    elif cmd == "instagram":
        img_url = sys.argv[2]
        cap = sys.argv[3] if len(sys.argv) > 3 else ""
        result = post_to_instagram(img_url, cap)
        print(f"Posted to Instagram: {result}")

    elif cmd == "refresh-token":
        result = refresh_access_token()
        print(f"New token info: {result}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
