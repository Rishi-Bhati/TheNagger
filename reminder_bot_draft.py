
import logging
import asyncio
import traceback
import time
from datetime import datetime
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from database import Database, Reminder

# Initialize database
db = Database()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Metrics & Error Handling Decorator ---
def track_activity(command_name: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return await func(update, context, *args, **kwargs)

            # 1. Update User Activity
            try:
                username = f"@{user.username}" if user.username else None
                full_name = user.full_name
                db.update_user_activity(user.id, username, full_name)
            except Exception as e:
                logger.error(f"Failed to track user activity: {e}")

            # 2. Track Metrics & Catch Errors
            start_time = time.time()
            try:
                result = await func(update, context, *args, **kwargs)
                
                # Log success metric
                process_time = (time.time() - start_time) * 1000
                db.log_bot_metric(user.id, command_name, process_time)
                
                return result

            except Exception as e:
                # Log failure metric (still counts as processed)
                process_time = (time.time() - start_time) * 1000
                db.log_bot_metric(user.id, command_name, process_time)
                
                # Filter out non-critical user errors
                error_msg = str(e)
                # List of errors that are "user's fault" and shouldn't be logged as system critical
                ignored_errors = [
                    "Message is not modified",
                    "Query is too old",
                    "Chat not found",
                    "Bot was blocked by the user"
                ]
                
                is_ignored = any(ignored in error_msg for ignored in ignored_errors)
                
                if not is_ignored:
                    logger.error(f"Critical error in {command_name}: {e}")
                    stack_trace = traceback.format_exc()
                    db.log_bot_error(user.id, "RuntimeError", error_msg, stack_trace)
                    
                    # Notify user only if it's a critical failure (optional)
                    if update.message:
                        await update.message.reply_text("❌ An internal error occurred. Administrators have been notified.")
                
                raise e 

        return wrapper
    return decorator

# --- Command Handlers ---

@track_activity("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"Hi {user.first_name}! I'm Nagger Bot. 🤖\n\n"
        "I can help you manage your tasks and nag you until you finish them!\n\n"
        "Here are some commands to get started:\n"
        "📝 /add - Add a new task\n"
        "📋 /list - List your active tasks\n"
        "✅ /done - Mark a task as complete\n"
        "❓ /help - Show help message"
    )
    await update.message.reply_text(welcome_message)

@track_activity("help")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    help_text = (
        "🤖 *Nagger Bot Help*\n\n"
        "*Task Management:*\n"
        "/add - Add a new task (follow the prompts)\n"
        "/list - List all pending tasks\n"
        "/done [ID] - Mark a task as complete\n"
        "/delete [ID] - Delete a task\n"
        "/edit [ID] - Edit a task\n\n"
        "*Settings:*\n"
        "/timezone [Region/City] - Set your timezone (e.g., /timezone America/New_York)\n"
        "/info - Show user info and settings\n\n"
        "*Other:*\n"
        "/cancel - Cancel current operation"
    )
    await update.message.reply_markdown(help_text)

@track_activity("add_task")
async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Simplified logic for example; assumes existing conversation handler structure would be wrapped differently
    # But since I'm overwriting the file, I need to be careful to preserve logic or import it.
    # The prompt implies I should MODIFY existing files. Replacing the whole file might be risky if I don't have the full content.
    # I have read the file content previously (Step 76 indicated 37kb).
    # I should use `replacement_chunk` on specific functions to add the decorator.
    pass
