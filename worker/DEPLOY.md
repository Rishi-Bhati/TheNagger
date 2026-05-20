# Nagger Bot — Deployment Guide

## Prerequisites
- A [Telegram Bot token](https://t.me/BotFather)
- A [Supabase](https://supabase.com) project (free tier works)
- [Node.js](https://nodejs.org) installed (for Wrangler CLI)
- A [Cloudflare account](https://dash.cloudflare.com) (free)

---

## Step 1 — Database Setup (Supabase)

1. Open your Supabase project dashboard → **SQL Editor** → **New Query**
2. Paste the entire contents of `supabase_setup.sql` and click **Run**
3. Confirm it completes without errors

---

## Step 2 — Configure `wrangler.toml`

Replace the `SUPABASE_URL` with your own project's URL:

```toml
[vars]
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
```

Your project URL is found in **Supabase Dashboard → Project Settings → API**.

---

## Step 3 — Set Secrets via Wrangler CLI

```bash
cd worker
npx wrangler secret put TELEGRAM_TOKEN
# paste your Telegram Bot token from BotFather

npx wrangler secret put SUPABASE_KEY
# paste your Supabase service_role key
# (Supabase Dashboard → Project Settings → API → service_role)
```

> ⚠️ **Never** put real tokens in `wrangler.toml` or any file that gets committed.

---

## Step 4 — Deploy

```bash
cd worker
npx wrangler deploy
```

You'll see output ending in:
```
Deployed nagger-bot triggers
  https://<worker-name>.<your-subdomain>.workers.dev
  schedule: * * * * *
```

---

## Step 5 — Register the Telegram Webhook

Tell Telegram to push all messages to your Worker instead of polling:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-worker-url>"
```

You should get: `{"ok":true,"result":true,"description":"Webhook was set"}`

Verify it any time:
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo"
```

---

## Step 6 — Test

Send `/start` to your bot on Telegram. Try:

```
/add Buy milk, in 10 minutes, 1m
```

It should confirm the task and start reminding you every minute.

---

## Updating / Redeploying

Any code change is live after:
```bash
cd worker && npx wrangler deploy
```

Secrets only need to be set once — they persist across deploys.
