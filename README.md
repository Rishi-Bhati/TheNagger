# Nagger Bot 🤖

> My brain has the memory of a goldfish. I forget stuff within minutes, so I built something that literally **annoys me until I do the damn task**. Less of a to-do list, more of a personal bully that keeps nagging me — basically my own toxic productivity buddy.

---

## What It Does

Nagger Bot is a **Telegram bot** that keeps pinging you with reminders until you actually mark a task as done. It runs completely free on Cloudflare Workers — no server needed, no bill, no downtime.

### Features
- ⚡ **Quick Add** — one-liner task creation with natural language
- 🌍 **Timezone support** — set via GPS or text, reminders always fire at the right local time
- 🔔 **Any frequency** — every minute, every hour, or daily
- 🕐 **Active hours** — only nag during your waking hours (e.g. 08:00–22:00)
- 📈 **Escalation** — reminders double in frequency as the deadline approaches
- 🚨 **Overdue nagging** — missed the deadline? It keeps bothering you until you `/done` it
- 👤 **Multi-user** — every user gets their own IDs starting from 1

---

## Commands

| Command | Description | Example |
|---|---|---|
| `/add Title, Deadline, Freq` | Quick add (primary) | `/add Buy milk, in 2 hours, 30m` |
| `/d` | Guided step-by-step wizard | `/d` |
| `/list` | View all active tasks | `/list` |
| `/done <ID>` | Mark task as completed | `/done 3` |
| `/delete <ID>` | Delete a task | `/delete 3` |
| `/edit <ID> field value` | Edit a task inline | `/edit 3 freq 1h` |
| `/test <ID>` | Fire a test reminder now | `/test 3` |
| `/timezone` | Set your timezone (GPS or text) | `/timezone` |
| `/clear` | Delete all your tasks | `/clear` |
| `/help` | Full help message | `/help` |

### Quick Add format
```
/add <Title>, <Deadline>, <Frequency>
```

**Deadline examples:** `in 10 minutes` · `tomorrow 5pm` · `today at 6pm` · `2025-12-25 15:30`

**Frequency shortcuts:** `1m` `15m` `30m` `45m` `1h` `2h` `4h` `6h` `12h` `daily`

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Cloudflare Workers (Python via Pyodide/WebAssembly) |
| **Language** | Python 3 (zero pip packages — 58 KB total) |
| **Database** | Supabase (PostgreSQL + REST API) |
| **Messaging** | Telegram Bot API (webhooks) |
| **Scheduling** | Cloudflare Cron Triggers (`* * * * *`) |

### Why serverless?
The original bot ran on Render and used APScheduler + asyncpg + python-telegram-bot (100+ MB of dependencies). It spun down after inactivity, causing missed reminders and 30-60s cold starts.

The new architecture:
- **No server to manage** — Cloudflare runs everything
- **Always on** — cron fires every minute regardless
- **Zero cost** — 100k requests/day free
- **58 KB** total deploy size (vs 100+ MB before)

---

## Self-Hosting / Deploy Your Own

### Prerequisites
- A [Telegram Bot token](https://t.me/BotFather)
- A [Supabase](https://supabase.com) project (free tier works)
- [Node.js](https://nodejs.org) (for Wrangler CLI)

### 1 — Database setup
Run `worker/supabase_setup.sql` in your Supabase project's **SQL Editor**.

### 2 — Configure
Edit `worker/wrangler.toml` and replace the `SUPABASE_URL` with your project URL:
```toml
[vars]
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
```

### 3 — Set secrets (never hardcode these)
```bash
cd worker
npx wrangler secret put TELEGRAM_TOKEN   # your bot token from BotFather
npx wrangler secret put SUPABASE_KEY     # your Supabase service_role key
```

### 4 — Deploy
```bash
cd worker
npx wrangler deploy
```

### 5 — Register the webhook with Telegram
```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<your-worker>.workers.dev"
```

That's it. The bot is live.

---

## Project Structure

```
worker/
├── wrangler.toml           # Cloudflare config (crons, env vars)
├── supabase_setup.sql      # Run once to create DB tables
└── src/
    ├── entry.py            # Entrypoint: fetch() webhook + scheduled() cron
    └── lib/
        ├── commands.py         # All /command handlers
        ├── reminder_engine.py  # Cron logic — who gets nagged and when
        ├── supabase_client.py  # Database layer (Supabase REST API)
        ├── telegram_api.py     # Telegram Bot API wrapper
        ├── cf_fetch.py         # HTTP client (Cloudflare's built-in fetch)
        ├── cf_tz.py            # Timezone resolver (no pytz/zoneinfo needed)
        ├── utils.py            # Date parsers, formatters
        └── timezone_lookup.py  # GPS coordinates → timezone name
```

---

## License

MIT — see [license](license)
