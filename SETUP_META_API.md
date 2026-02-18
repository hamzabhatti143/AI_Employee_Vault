# Meta API Setup Guide (Facebook + Instagram Posting)

## Prerequisites
- A **Facebook Page** you admin
- An **Instagram Business** or **Creator** account linked to that Facebook Page
- A **Meta Developer** account (free)

---

## Step 1: Create a Meta App

1. Go to https://developers.facebook.com/apps/
2. Click **Create App** → choose **Business** type → **Next**
3. Name it (e.g. "AI Employee Vault") → select your Business portfolio → **Create**

## Step 2: Add Facebook Login Product (for token generation)

1. In the app dashboard, click **Add Product** → **Facebook Login** → **Set Up**
2. Skip the quickstart — you only need this to generate tokens

## Step 3: Generate a Page Access Token

1. Go to **Graph API Explorer**: https://developers.facebook.com/tools/explorer/
2. Select your app from the **Application** dropdown
3. Click **Generate Access Token** → log in → grant permissions
4. Required permissions:
   - `pages_manage_posts` — post to your Page
   - `pages_read_engagement` — read Page info
   - `instagram_basic` — read IG profile
   - `instagram_content_publish` — post to Instagram
5. Select your **Page** from the "User or Page" dropdown
6. Copy the resulting **Page Access Token**

## Step 4: Exchange for a Long-Lived Token (60 days)

Short-lived tokens expire in ~1 hour. Exchange it:

```bash
curl -s "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=YOUR_APP_ID&\
client_secret=YOUR_APP_SECRET&\
fb_exchange_token=SHORT_LIVED_TOKEN" | python3 -m json.tool
```

Copy the `access_token` from the response — this is your **long-lived Page Access Token**.

## Step 5: Get Your Page ID

```bash
curl -s "https://graph.facebook.com/v21.0/me?access_token=YOUR_LONG_LIVED_TOKEN" | python3 -m json.tool
```

Note the `id` field — this is your `FACEBOOK_PAGE_ID`.

## Step 6: Get Your Instagram User ID

```bash
curl -s "https://graph.facebook.com/v21.0/YOUR_PAGE_ID?fields=instagram_business_account&access_token=YOUR_LONG_LIVED_TOKEN" | python3 -m json.tool
```

The `instagram_business_account.id` is your `INSTAGRAM_USER_ID`.

## Step 7: Fill in `watchers/.env`

```env
META_APP_ID=123456789
META_APP_SECRET=abcdef123456
FACEBOOK_PAGE_ID=987654321
FACEBOOK_PAGE_ACCESS_TOKEN=EAAxxxxxxx...
FACEBOOK_TOKEN_EXPIRY=2026-04-15
INSTAGRAM_USER_ID=17841400000000
META_GRAPH_API_VERSION=v21.0
```

Set `FACEBOOK_TOKEN_EXPIRY` to ~60 days from today so the system can warn you before it expires.

## Step 8: Test

```bash
cd /mnt/d/ai-employee-vault/watchers
.venv/bin/python social_utils.py facebook "Hello from AI Employee Vault!"
```

## Token Refresh

Long-lived tokens last 60 days. Before expiry, refresh:

```bash
cd /mnt/d/ai-employee-vault/watchers
.venv/bin/python social_utils.py refresh-token
```

Then update `FACEBOOK_PAGE_ACCESS_TOKEN` and `FACEBOOK_TOKEN_EXPIRY` in `.env`.

## Permissions Summary

| Permission | Purpose |
|---|---|
| `pages_manage_posts` | Create posts on Facebook Page |
| `pages_read_engagement` | Read Page metadata |
| `instagram_basic` | Read Instagram account info |
| `instagram_content_publish` | Publish photos to Instagram |

## Instagram Posting Requirements

- Image must be a **publicly accessible URL** (not a local file)
- Supported formats: JPEG, PNG (JPEG recommended)
- Image must be **< 8MB**
- Caption max **2200 characters**
- The Instagram account must be **Business** or **Creator** type
- The Instagram account must be **linked to the Facebook Page**
