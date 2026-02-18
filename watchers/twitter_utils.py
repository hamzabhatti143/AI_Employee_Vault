"""Utilities for Twitter/X API via Tweepy."""

import os
import logging
from pathlib import Path

import tweepy
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(Path(__file__).parent / ".env")


def _get_client():
    """Get authenticated Tweepy Client (v2 API)."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")

    missing = []
    if not api_key: missing.append("TWITTER_API_KEY")
    if not api_secret: missing.append("TWITTER_API_SECRET")
    if not access_token: missing.append("TWITTER_ACCESS_TOKEN")
    if not access_secret: missing.append("TWITTER_ACCESS_SECRET")
    if missing:
        raise ValueError(f"Missing Twitter env vars: {', '.join(missing)}")

    return tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
    )


def _get_api_v1():
    """Get authenticated Tweepy API (v1.1) for media uploads."""
    api_key = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_secret = os.getenv("TWITTER_ACCESS_SECRET")

    auth = tweepy.OAuthHandler(api_key, api_secret)
    auth.set_access_token(access_token, access_secret)
    return tweepy.API(auth)


def post_tweet(text: str) -> dict:
    """Post a tweet.

    Args:
        text: Tweet text (max 280 chars for free tier).

    Returns:
        Dict with tweet 'id' and 'text'.
    """
    client = _get_client()
    response = client.create_tweet(text=text)
    tweet_id = response.data["id"]
    logger.info(f"Tweet posted: {tweet_id}")
    return {"id": tweet_id, "text": text}


def get_mentions(count: int = 10) -> list:
    """Get recent mentions.

    Args:
        count: Number of mentions to fetch.

    Returns:
        List of mention dicts with 'id', 'text', 'author_id'.
    """
    api = _get_api_v1()
    mentions = api.mentions_timeline(count=count)
    return [
        {
            "id": str(m.id),
            "text": m.text,
            "author": f"@{m.user.screen_name}",
            "created_at": str(m.created_at),
        }
        for m in mentions
    ]


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python twitter_utils.py tweet 'Hello world'")
        print("  python twitter_utils.py mentions")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "tweet":
        text = sys.argv[2] if len(sys.argv) > 2 else "Hello from AI Employee Vault!"
        result = post_tweet(text)
        print(f"Posted: {result}")

    elif cmd == "mentions":
        mentions = get_mentions()
        for m in mentions:
            print(f"  {m['author']}: {m['text'][:100]}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
