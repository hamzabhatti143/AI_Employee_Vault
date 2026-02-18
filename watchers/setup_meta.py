"""
Interactive Meta API Setup — connects Facebook & Instagram in a few simple steps.
Run: python setup_meta.py
"""
import os
import sys
import webbrowser
import time
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv, set_key

ENV_FILE = Path(__file__).parent / ".env"
GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Colors for terminal
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════╗
║   Meta API Setup — Facebook & Instagram Posting  ║
║   Follow the steps below. I'll do the rest!      ║
╚══════════════════════════════════════════════════╝{RESET}
""")


def step(num, title):
    print(f"\n{BOLD}{GREEN}━━━ Step {num}: {title} ━━━{RESET}\n")


def info(msg):
    print(f"  {CYAN}→{RESET} {msg}")


def success(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}!{RESET} {msg}")


def error(msg):
    print(f"  {RED}✗{RESET} {msg}")


def ask(prompt, required=True):
    while True:
        val = input(f"  {BOLD}{prompt}{RESET}: ").strip()
        if val or not required:
            return val
        print(f"  {RED}This field is required. Please try again.{RESET}")


def ask_yn(prompt):
    while True:
        val = input(f"  {BOLD}{prompt} (y/n){RESET}: ").strip().lower()
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False


def open_url(url):
    """Open URL in browser (works in WSL too)."""
    info(f"Opening: {url}")
    try:
        # Try WSL way first
        os.system(f'cmd.exe /c start "" "{url}" 2>/dev/null')
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            warn(f"Could not open browser. Please open manually:\n    {url}")
    time.sleep(2)


def save_env(key, value):
    """Save a key to .env file."""
    set_key(str(ENV_FILE), key, value)
    success(f"Saved {key} to .env")


def test_token(token):
    """Test if a token is valid by calling /me."""
    try:
        resp = requests.get(f"{GRAPH_BASE}/me", params={"access_token": token}, timeout=10)
        if resp.ok:
            return resp.json()
        return None
    except Exception:
        return None


def get_pages(token):
    """Get list of pages the user manages."""
    try:
        resp = requests.get(
            f"{GRAPH_BASE}/me/accounts",
            params={"access_token": token},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("data", [])
        return []
    except Exception:
        return []


def exchange_for_long_lived(app_id, app_secret, short_token):
    """Exchange short-lived token for long-lived (60 day) token."""
    resp = requests.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    if resp.ok:
        return resp.json()
    error(f"Token exchange failed: {resp.text}")
    return None


def get_page_long_lived_token(page_id, user_long_token):
    """Get a long-lived page token (never expires) from a long-lived user token."""
    resp = requests.get(
        f"{GRAPH_BASE}/{page_id}",
        params={"fields": "access_token", "access_token": user_long_token},
        timeout=10,
    )
    if resp.ok:
        return resp.json().get("access_token")
    return None


def get_instagram_id(page_id, token):
    """Get the Instagram Business account ID linked to a page."""
    resp = requests.get(
        f"{GRAPH_BASE}/{page_id}",
        params={"fields": "instagram_business_account", "access_token": token},
        timeout=10,
    )
    if resp.ok:
        data = resp.json()
        ig = data.get("instagram_business_account", {})
        return ig.get("id")
    return None


def main():
    load_dotenv(ENV_FILE)
    banner()

    # ── Step 1: Create Meta App ──
    step(1, "Create a Meta App")
    info("You need a Meta Developer App to connect Facebook & Instagram.")
    info("If you already have one, skip this step.\n")

    if ask_yn("Do you already have a Meta App?"):
        success("Great! Moving on.")
    else:
        info("I'll open the Meta Developer portal for you.")
        info("Create a new app → choose 'Business' type → name it anything.\n")
        input(f"  {BOLD}Press Enter to open Meta Developer portal...{RESET}")
        open_url("https://developers.facebook.com/apps/create/")
        info("After creating the app, come back here.\n")
        input(f"  {BOLD}Press Enter when your app is created...{RESET}")
        success("App created!")

    # ── Step 2: Get App ID and Secret ──
    step(2, "App ID & Secret")
    info("Find these in your Meta App Dashboard → Settings → Basic\n")

    existing_id = os.getenv("META_APP_ID", "")
    existing_secret = os.getenv("META_APP_SECRET", "")

    if existing_id and existing_secret:
        info(f"Found existing App ID: {existing_id[:6]}...")
        if ask_yn("Use existing App ID and Secret?"):
            app_id = existing_id
            app_secret = existing_secret
        else:
            app_id = ask("App ID")
            app_secret = ask("App Secret")
    else:
        if not ask_yn("Do you have your App ID and Secret ready?"):
            input(f"  {BOLD}Press Enter to open App Settings...{RESET}")
            open_url("https://developers.facebook.com/apps/")
            info("Go to your app → Settings → Basic\n")
            input(f"  {BOLD}Press Enter when ready...{RESET}")

        app_id = ask("App ID")
        app_secret = ask("App Secret")

    save_env("META_APP_ID", app_id)
    save_env("META_APP_SECRET", app_secret)

    # ── Step 3: Generate Access Token ──
    step(3, "Generate Access Token")
    info("I'll open the Graph API Explorer where you can generate a token.")
    info("Select your app, then click 'Generate Access Token'.")
    info("Grant ALL these permissions when asked:\n")
    print(f"    {BOLD}pages_manage_posts{RESET}")
    print(f"    {BOLD}pages_read_engagement{RESET}")
    print(f"    {BOLD}instagram_basic{RESET}")
    print(f"    {BOLD}instagram_content_publish{RESET}\n")

    input(f"  {BOLD}Press Enter to open Graph API Explorer...{RESET}")
    open_url(f"https://developers.facebook.com/tools/explorer/?app_id={app_id}")

    info("After granting permissions, copy the Access Token shown at the top.\n")
    short_token = ask("Paste your Access Token here")

    # Verify the token works
    info("Verifying token...")
    me = test_token(short_token)
    if me:
        success(f"Token works! Logged in as: {me.get('name', 'Unknown')}")
    else:
        error("Token doesn't seem valid. Continuing anyway — you can retry later.")

    # ── Step 4: Exchange for Long-Lived Token ──
    step(4, "Exchange for Long-Lived Token (automatic)")
    info("Converting your short-lived token to a 60-day token...\n")

    result = exchange_for_long_lived(app_id, app_secret, short_token)
    if result and result.get("access_token"):
        long_user_token = result["access_token"]
        expires_in = result.get("expires_in", 5184000)
        expiry_date = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).strftime("%Y-%m-%d")
        success(f"Got long-lived user token (expires: {expiry_date})")
    else:
        warn("Could not exchange token. Using original token (may expire in 1 hour).")
        long_user_token = short_token
        expiry_date = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%d")

    # ── Step 5: Select Facebook Page ──
    step(5, "Select Your Facebook Page (automatic)")
    info("Fetching your pages...\n")

    pages = get_pages(long_user_token)
    if not pages:
        warn("No pages found. Make sure you admin a Facebook Page.")
        page_id = ask("Enter your Facebook Page ID manually")
        page_token = long_user_token
    elif len(pages) == 1:
        page = pages[0]
        page_id = page["id"]
        page_token = page.get("access_token", long_user_token)
        success(f"Found page: {page['name']} (ID: {page_id})")
    else:
        info("Multiple pages found:\n")
        for i, page in enumerate(pages, 1):
            print(f"    {BOLD}{i}.{RESET} {page['name']} (ID: {page['id']})")
        print()
        while True:
            choice = ask(f"Select page (1-{len(pages)})")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(pages):
                    page = pages[idx]
                    page_id = page["id"]
                    page_token = page.get("access_token", long_user_token)
                    success(f"Selected: {page['name']}")
                    break
            except ValueError:
                pass
            error("Invalid choice, try again.")

    # Get never-expiring page token
    info("Getting permanent page token...")
    permanent_token = get_page_long_lived_token(page_id, long_user_token)
    if permanent_token:
        page_token = permanent_token
        expiry_date = "2099-12-31"  # Page tokens from long-lived user tokens don't expire
        success("Got permanent page access token (does not expire!)")
    else:
        warn("Could not get permanent token. Using 60-day token instead.")

    save_env("FACEBOOK_PAGE_ID", page_id)
    save_env("FACEBOOK_PAGE_ACCESS_TOKEN", page_token)
    save_env("FACEBOOK_TOKEN_EXPIRY", expiry_date)

    # ── Step 6: Instagram Setup ──
    step(6, "Connect Instagram (automatic)")
    info("Looking for Instagram Business account linked to your page...\n")

    ig_id = get_instagram_id(page_id, page_token)
    if ig_id:
        success(f"Found Instagram account (ID: {ig_id})")
        save_env("INSTAGRAM_USER_ID", ig_id)
    else:
        warn("No Instagram account linked to this page.")
        info("To link one:")
        info("1. Switch your Instagram to a Creator or Business account")
        info("2. In Instagram settings → Account → Linked Accounts → Facebook")
        info("3. Link it to your Facebook Page")
        info("4. Run this setup again\n")
        if ask_yn("Do you want to enter an Instagram User ID manually?"):
            ig_id = ask("Instagram User ID")
            save_env("INSTAGRAM_USER_ID", ig_id)

    save_env("META_GRAPH_API_VERSION", GRAPH_API_VERSION)

    # ── Step 7: Test ──
    step(7, "Test Connection")

    if ask_yn("Send a test post to Facebook?"):
        info("Posting to Facebook...")
        try:
            resp = requests.post(
                f"{GRAPH_BASE}/{page_id}/feed",
                data={"message": "Hello from AI Employee Vault! (test post — you can delete this)"},
                headers={"Authorization": f"Bearer {page_token}"},
                timeout=30,
            )
            if resp.ok:
                post_id = resp.json().get("id")
                success(f"Facebook test post created! (ID: {post_id})")
            else:
                error(f"Facebook post failed: {resp.json().get('error', {}).get('message', resp.text)}")
        except Exception as e:
            error(f"Facebook post failed: {e}")
    else:
        info("Skipping Facebook test.")

    # ── Done! ──
    print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════╗
║           Setup Complete!                        ║
╚══════════════════════════════════════════════════╝{RESET}

  Your credentials are saved in: {ENV_FILE}

  {BOLD}You can now use:{RESET}
    • {CYAN}post_facebook{RESET}  — MCP tool to post to Facebook
    • {CYAN}post_instagram{RESET} — MCP tool to post to Instagram

  {BOLD}Test manually:{RESET}
    cd /mnt/d/ai-employee-vault/watchers
    .venv/bin/python social_utils.py facebook "Hello World!"
""")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Setup cancelled.{RESET}\n")
        sys.exit(0)
