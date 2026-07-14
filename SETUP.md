# WHOOP Quest Setup

## 1. Fork this repo

Click Fork → your account.

## 2. Create a WHOOP OAuth app

1. Go to https://developer.whoop.com/
2. Create an app, set redirect URI to `http://localhost:8080/callback`
3. Request scopes: `offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement`
4. Copy your `CLIENT_ID` and `CLIENT_SECRET`

## 3. Get your WHOOP tokens

```bash
# 1. Get auth URL
curl "https://api.prod.whoop.com/oauth/oauth2/auth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8080/callback&scope=offline%20read:profile%20read:cycles%20read:recovery%20read:sleep%20read:workout%20read:body_measurement"

# 2. Open the URL, authorize, copy the ?code=... from the redirect

# 3. Exchange code for tokens
curl -X POST https://api.prod.whoop.com/oauth/oauth2/token \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_CODE" \
  -d "redirect_uri=http://localhost:8080/callback" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET"
```

Save the `access_token` and `refresh_token` from the response.

## 4. Add GitHub Secrets

In your forked repo → Settings → Secrets and variables → Actions → New repository secret, add:

- `WHOOP_ACCESS_TOKEN`
- `WHOOP_REFRESH_TOKEN`
- `WHOOP_CLIENT_ID`
- `WHOOP_CLIENT_SECRET`

## 5. Enable GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: `main` → Folder: `/ (root)`

Your game will be live at `https://YOUR_USERNAME.github.io/whoop-quest/` within a few minutes.

## 6. Run the first sync

Actions tab → "Sync WHOOP" → Run workflow

This pulls your WHOOP data into `data/whoop.json` and commits it. The app reads that file — no backend needed.

The sync runs automatically every day at 9am ET after that.

---

## Local dev

Just open `index.html` in your browser. To test with fresh data:

```bash
export WHOOP_ACCESS_TOKEN=...
export WHOOP_REFRESH_TOKEN=...
export WHOOP_CLIENT_ID=...
export WHOOP_CLIENT_SECRET=...
python scripts/sync_whoop.py
```

Then refresh `index.html`.
