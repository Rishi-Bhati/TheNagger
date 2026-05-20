"""
lib/telegram_api.py — Telegram Bot API using CF built-in fetch (no httpx).
"""
import logging
from .cf_fetch import cf_get, cf_post

logger = logging.getLogger(__name__)


class TelegramAPI:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    async def send_message(self, chat_id, text, parse_mode="Markdown", reply_markup=None):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            await cf_post(f"{self.base}/sendMessage", data=payload)
        except Exception as e:
            logger.error(f"sendMessage failed: {e}")

    async def send_message_with_inline_keyboard(self, chat_id, text, keyboard, parse_mode="Markdown"):
        await self.send_message(chat_id, text, parse_mode=parse_mode,
                                reply_markup={"inline_keyboard": keyboard})

    async def send_message_with_reply_keyboard(self, chat_id, text, keyboard, one_time=True, parse_mode="Markdown"):
        await self.send_message(chat_id, text, parse_mode=parse_mode,
                                reply_markup={"keyboard": keyboard,
                                              "one_time_keyboard": one_time,
                                              "resize_keyboard": True})

    async def remove_reply_keyboard(self, chat_id, text):
        await self.send_message(chat_id, text, reply_markup={"remove_keyboard": True})

    async def answer_callback_query(self, callback_query_id, text=""):
        try:
            await cf_post(f"{self.base}/answerCallbackQuery",
                          data={"callback_query_id": callback_query_id, "text": text})
        except Exception as e:
            logger.error(f"answerCallbackQuery failed: {e}")

    async def edit_message_text(self, chat_id, message_id, text, parse_mode="Markdown", reply_markup=None):
        payload = {"chat_id": chat_id, "message_id": message_id,
                   "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            await cf_post(f"{self.base}/editMessageText", data=payload)
        except Exception as e:
            logger.error(f"editMessageText failed: {e}")
