"""
src/entry.py — Cloudflare Worker entrypoint.

Two handlers:
  fetch()     — Telegram webhook (incoming user messages)
  scheduled() — Cron trigger (fires every minute to check & send reminders)
"""
import logging

from workers import WorkerEntrypoint, Response

from lib.telegram_api import TelegramAPI
from lib.supabase_client import SupabaseDB
from lib.commands import handle_update
from lib.reminder_engine import check_and_send_reminders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Default(WorkerEntrypoint):

    async def fetch(self, request):
        """Handle incoming Telegram webhook POST requests & Dashboard API requests."""
        env = self.env
        url = request.url
        path = "/" + url.split("/", 3)[-1].split("?")[0] if "/" in url else "/"
        
        # Dashboard API routes (Pre-flight OPTIONS or GET/POST/PATCH/DELETE)
        if request.method == "OPTIONS" or path.startswith("/api/"):
            from lib.web_router import route_api
            return await route_api(request, path, env)

        if request.method == "GET":
            return Response("Nagger Bot is alive 🤖", status=200)

        if request.method != "POST":
            return Response("Method not allowed", status=405)

        tg = TelegramAPI(env.TELEGRAM_TOKEN)
        db = SupabaseDB(env.SUPABASE_URL, env.SUPABASE_KEY)

        try:
            update = await request.json()
            await handle_update(update, tg, db)
        except Exception as e:
            logger.error(f"Error handling update: {e}")

        # Always return 200 so Telegram doesn't retry
        return Response("OK", status=200)

    async def scheduled(self, controller, env, ctx):
        """Cron trigger — runs every minute to send due reminders."""
        my_env = self.env
        tg = TelegramAPI(my_env.TELEGRAM_TOKEN)
        db = SupabaseDB(my_env.SUPABASE_URL, my_env.SUPABASE_KEY)

        try:
            sent = await check_and_send_reminders(tg, db)
            logger.info(f"Cron: sent {sent} reminder(s)")
        except Exception as e:
            logger.error(f"Cron error: {e}")
