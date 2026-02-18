# Social Media Posting Guide (Facebook & Instagram)

## Accounts Connected

| Platform  | Account          | Page/Profile ID      |
|-----------|------------------|----------------------|
| Facebook  | Agent Builder    | `1048492888340021`   |
| Instagram | @hamzaabtach90   | `17841448111605964`  |

---

## Method 1: MCP Tools (via Claude Code)

Ask Claude to use the MCP tools directly in conversation.

### Facebook Post (text only)

> "Post to Facebook: We build custom AI agents for businesses. Contact us today!"

Claude will call `post_facebook` tool.

### Facebook Post (with image)

> "Post to Facebook with this image: https://example.com/image.jpg and message: Launching our new service!"

Claude will call `post_facebook` with `image_url` parameter.

### Instagram Post (image required)

> "Post to Instagram with image https://example.com/photo.jpg and caption: Building the future with AI #agentbuilder"

Claude will call `post_instagram` tool.

---

## Method 2: Command Line

Run from the `watchers/` directory:

```bash
cd /mnt/d/ai-employee-vault/watchers
```

### Facebook Post (text only)

```bash
.venv/bin/python social_utils.py facebook "Your post message here"
```

### Facebook Post (with image)

```bash
.venv/bin/python social_utils.py facebook "Your caption here" "https://example.com/image.jpg"
```

### Instagram Post

```bash
.venv/bin/python social_utils.py instagram "https://example.com/image.jpg" "Your caption here #hashtag"
```

---

## Method 3: Python Script

```python
from social_utils import post_to_facebook, post_to_instagram

# Facebook - text only
post_to_facebook("Hello from Agent Builder!")

# Facebook - with image
post_to_facebook("Check this out!", image_url="https://example.com/image.jpg")

# Instagram - image required
post_to_instagram(
    image_url="https://example.com/photo.jpg",
    caption="Building AI solutions #agentbuilder #automation"
)
```

---

## Instagram Requirements

- Image must be a **publicly accessible URL** (no local files)
- URL must be **direct** (no redirects)
- Supported formats: **JPEG** (recommended), PNG
- Image size: **< 8MB**
- Caption: max **2200 characters**
- Account must be **Business** or **Creator** type

---

## Token Management

The access token expires every **60 days**. Current expiry: check `FACEBOOK_TOKEN_EXPIRY` in `watchers/.env`.

### Check token expiry

```bash
grep FACEBOOK_TOKEN_EXPIRY /mnt/d/ai-employee-vault/watchers/.env
```

### Refresh token (before it expires)

```bash
cd /mnt/d/ai-employee-vault/watchers
.venv/bin/python social_utils.py refresh-token
```

Then update `FACEBOOK_PAGE_ACCESS_TOKEN` and `FACEBOOK_TOKEN_EXPIRY` in `.env`.

### If token has already expired

1. Go to https://developers.facebook.com/tools/explorer/
2. Select app **"AI_Employee_Vault"**
3. Select all permissions (especially `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`)
4. Generate token
5. In Graph API Explorer, switch to **Page** "Agent Builder" to get a Page token
6. Or use the user token and run:

```bash
.venv/bin/python -c "
import urllib.request, json, os
from dotenv import load_dotenv
load_dotenv()
token = 'PASTE_YOUR_USER_TOKEN_HERE'
version = 'v21.0'
page_id = '1048492888340021'
app_id = os.getenv('META_APP_ID')
app_secret = os.getenv('META_APP_SECRET')

# Get page token
url = f'https://graph.facebook.com/{version}/{page_id}?fields=access_token&access_token={token}'
resp = urllib.request.urlopen(url)
page_token = json.loads(resp.read())['access_token']

# Exchange for long-lived
url2 = f'https://graph.facebook.com/{version}/oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={page_token}'
resp2 = urllib.request.urlopen(url2)
ll_token = json.loads(resp2.read())['access_token']
print(f'New long-lived token: {ll_token}')
"
```

7. Update `FACEBOOK_PAGE_ACCESS_TOKEN` in `watchers/.env`
8. Set `FACEBOOK_TOKEN_EXPIRY` to 60 days from today

---

## Tips for Good Posts

### Facebook
- Text posts work fine, no image required
- Add a call-to-action (link, question, or contact info)
- Best posting times: 9 AM - 12 PM weekdays

### Instagram
- Every post **must** have an image
- Use relevant hashtags (up to 30, but 5-10 is optimal)
- Write engaging captions with a hook in the first line
- Use line breaks for readability

### Free Image Hosting (for Instagram)
If you need a public URL for an image, you can upload to:
- **Imgur**: https://imgur.com (free, no account needed)
- **Postimages**: https://postimages.org (free, direct links)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pages_manage_posts` missing | Re-generate token with this permission in Graph API Explorer |
| Instagram "media not ready" | The system waits up to 50 seconds automatically |
| Instagram "URI doesn't meet requirements" | Use a direct image URL (no redirects), JPEG format |
| Token expired | Run `social_utils.py refresh-token` or re-generate manually |
| `INSTAGRAM_USER_ID not set` | Check `watchers/.env` has `INSTAGRAM_USER_ID='17841448111605964'` |
