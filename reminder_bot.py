#!/usr/bin/env python3
import logging
import asyncio
import sys

# Fix for Windows asyncio loop policy to avoid WinError 995
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from datetime import datetime, timedelta
from threading import Thread
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
import pytz
from timezonefinder import TimezoneFinder

from config import TELEGRAM_BOT_TOKEN, DATABASE_URL
from database import Database
from reminder_scheduler import ReminderScheduler
from web_server import run_health_server
from utils import (
    parse_datetime,
    parse_frequency,
    format_task_list,
    validate_task_input,
    create_frequency_keyboard,
    create_time_selection_keyboard,
    escape_markdown
)
from models import FrequencyType

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Silence verbose libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Conversation states
TASK_TITLE, TASK_DESCRIPTION, TASK_DEADLINE = range(3)
REMINDER_FREQUENCY, REMINDER_START_TIME, REMINDER_END_TIME, REMINDER_ESCALATION = range(3, 7)
EDIT_CHOICE, EDIT_VALUE = range(7, 9)
TIMEZONE_LOCATION = 9

# --- Metrics & Error Handling Decorator ---
import time
import traceback
from functools import wraps
from typing import Callable, Any

def track_activity(command_name: str):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            if not user:
                return await func(self, update, context, *args, **kwargs)

            # 1. Update User Activity (Background Task)
            try:
                username = f"@{user.username}" if user.username else None
                full_name = user.full_name
                # Fire and forget - don't await
                asyncio.create_task(self.db.update_user_activity(user.id, username, full_name))
            except Exception as e:
                logger.error(f"Failed to track user activity: {e}")

            # 2. Track Metrics & Catch Errors
            start_time = time.time()
            try:
                result = await func(self, update, context, *args, **kwargs)
                
                # Log success metric (Background Task)
                process_time = (time.time() - start_time) * 1000
                asyncio.create_task(self.db.log_bot_metric(user.id, command_name, process_time))
                
                return result

            except Exception as e:
                # Log failure metric (Background Task)
                process_time = (time.time() - start_time) * 1000
                asyncio.create_task(self.db.log_bot_metric(user.id, command_name, process_time))
                
                # Filter out non-critical user errors
                error_msg = str(e)
                # List of errors that are "user's fault" and shouldn't be logged as system critical
                ignored_errors = [
                    "Message is not modified",
                    "Query is too old",
                    "Chat not found",
                    "Bot was blocked by the user",
                    "Invalid task ID",
                    "Invalid time format",
                    "Invalid deadline format",
                    "Task not found"
                ]
                
                is_ignored = any(ignored in error_msg for ignored in ignored_errors)
                
                if not is_ignored and not isinstance(e, ValueError): # Ignored value errors usually input related
                    logger.error(f"Critical error in {command_name}: {e}")
                    stack_trace = traceback.format_exc()
                    await self.db.log_bot_error(user.id, type(e).__name__, error_msg, stack_trace)
                    
                    # Notify user only if it's a critical failure
                    if update.message:
                         # Don't send for user errors, but for real crashes
                         pass 
                
                raise e 

        return wrapper
    return decorator


class ReminderBot:
    def __init__(self):
        self.db = Database(DATABASE_URL)
        self.application = None
        self.scheduler = None
        self.tf = TimezoneFinder()
        
    async def post_init(self, application: Application) -> None:
        """Initialize bot after application is built"""
        await self.db.connect()
        self.scheduler = ReminderScheduler(application.bot, self.db)
        await self.scheduler.start()
        logger.info("Bot initialized successfully")
        
    async def post_shutdown(self, application: Application) -> None:
        """Cleanup on shutdown"""
        await self.db.close()
    
    @track_activity("start")
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user = update.effective_user
        welcome_message = f"""
👋 Welcome to *Nagger Bot*, {user.mention_html()}!

I'm your personal reminder assistant that will keep nagging you until you complete your tasks! 

*Here's what I can do:*
• ⚡ `/q` - Quick add task (NEW! One command)
• 📝 `/add` - Add task with full customization
• 📋 `/list` - View all your active tasks
• ✅ `/done` - Mark a task as completed
• 🗑️ `/delete` - Delete a task
• 🧹 `/clear` - Clear all tasks and start fresh
• ❓ `/help` - Show detailed help

*Quick Start Example:*
`/q Buy groceries | in 2 hours | 30m`

This creates a task "Buy groceries" due in 2 hours with reminders every 30 minutes!

Type `/help` for more examples or `/q` to quickly add your first task.
        """
        
        await update.message.reply_html(welcome_message)
    
    @track_activity("help")
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a detailed help message"""
        help_text = """
👋 *Hi! I'm Nagger Bot.*
I'll keep bothering you until you get things done!

🌟 *Getting Started (The Basics)*
• `/add` - Start here! I'll ask you questions to set up your task.
• `/list` - See what you need to do.
• `/done <id>` - Tell me you finished a task (e.g., `/done 1`).
• `/timezone` - Set your time so I don't wake you up at 3 AM! 🌍

🚀 *Power User Features*
Want to be faster? Use Quick Add:
`/q <Title>, <Deadline>, <Frequency>`
_Ex: `/q Buy milk, 5pm, 30m`_

📋 *All Commands*
• `/start` - Restart me
• `/add` - Add task (Wizard mode)
• `/q` - Add task (Fast mode)
• `/list` - Show active tasks
• `/done <id>` - Complete task
• `/delete <id>` - Remove task
• `/edit <id>` - Modify task
• `/test <id>` - Send test reminder
• `/clear` - Delete EVERYTHING
• `/timezone` - Set location

💡 *Pro Tip:*
Use "natural language" for times!
• "in 10 minutes"
• "tomorrow at 5pm"
• "every 2 hours"
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def timezone_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start timezone selection"""
        user_id = update.effective_user.id
        current_tz = await self.db.get_user_timezone(user_id)
        
        keyboard = [
            [KeyboardButton("📍 Send Location", request_location=True)],
            [KeyboardButton("Manual Selection")]
        ]
        
        await update.message.reply_text(
            f"🌍 *Timezone Settings*\n\n"
            f"Current timezone: `{current_tz}`\n\n"
            "To set your timezone, you can:\n"
            "1. Share your location (Easiest)\n"
            "2. Select manually\n\n"
            "Tap 'Send Location' below or type 'Manual Selection'.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='Markdown'
        )
        return TIMEZONE_LOCATION

    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle location sharing for timezone detection"""
        user = update.effective_user
        location = update.message.location
        
        if location:
            timezone_str = self.tf.timezone_at(lng=location.longitude, lat=location.latitude)
            if timezone_str:
                await self.db.set_user_timezone(user.id, timezone_str)
                await update.message.reply_text(
                    f"✅ Timezone set to: `{timezone_str}`",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
        
        await update.message.reply_text(
            "❌ Could not determine timezone from location. Please try manual selection.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def handle_manual_timezone(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle manual timezone selection text"""
        text = update.message.text
        
        if text == "Manual Selection":
            # Show continent selection
            continents = ["America", "Europe", "Asia", "Australia", "Africa", "Pacific"]
            keyboard = []
            row = []
            for cont in continents:
                row.append(InlineKeyboardButton(cont, callback_data=f"tz_cont_{cont}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
                
            await update.message.reply_text(
                "Select your continent:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return TIMEZONE_LOCATION
            
        return ConversationHandler.END

    async def handle_timezone_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle timezone selection callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith("tz_cont_"):
            continent = data.split("_")[2]
            # Show major cities for continent (simplified list)
            cities = {
                "America": ["New_York", "Chicago", "Los_Angeles", "Toronto", "Sao_Paulo"],
                "Europe": ["London", "Paris", "Berlin", "Rome", "Moscow"],
                "Asia": ["Tokyo", "Shanghai", "Singapore", "Dubai", "Kolkata"],
                "Australia": ["Sydney", "Melbourne", "Perth"],
                "Africa": ["Cairo", "Johannesburg", "Lagos"],
                "Pacific": ["Auckland", "Fiji"]
            }
            
            keyboard = []
            row = []
            for city in cities.get(continent, []):
                tz_name = f"{continent}/{city}"
                row.append(InlineKeyboardButton(city.replace("_", " "), callback_data=f"tz_set_{tz_name}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)
            
            # Add back button
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="tz_back")])
            
            await query.edit_message_text(
                f"Select city in {continent}:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return TIMEZONE_LOCATION
            
        elif data.startswith("tz_set_"):
            timezone_str = data.split("_", 2)[2]
            user_id = update.effective_user.id
            await self.db.set_user_timezone(user_id, timezone_str)
            
            await query.edit_message_text(
                f"✅ Timezone set to: `{timezone_str}`",
                parse_mode='Markdown'
            )
            return ConversationHandler.END
            
        elif data == "tz_back":
            # Go back to continent selection
            return await self.handle_manual_timezone(update, context)
            
        return TIMEZONE_LOCATION
    
    # Task Management Commands
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the add task conversation"""
        user_id = update.effective_user.id
        timezone = await self.db.get_user_timezone(user_id)
        
        if timezone == 'UTC':
            await update.message.reply_text(
                "⚠️ *Timezone Not Set*\n\n"
                "You are currently using UTC time. For accurate reminders, please set your timezone first using `/timezone`.\n\n"
                "You can continue, but times will be treated as UTC.",
                parse_mode='Markdown'
            )
            
        await update.message.reply_text(
            "📝 *Creating a new task*\n\n"
            "Please enter the *task title*:\n"
            "(e.g., 'Finish project report')\n\n"
            "_Type /cancel at any time to abort._",
            parse_mode='Markdown'
        )
        return TASK_TITLE
    
    async def add_task_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle task title input"""
        context.user_data['task_title'] = update.message.text
        
        await update.message.reply_text(
            "📄 Great! Now enter a *description* for the task:\n"
            "(or type 'skip' to skip this step)",
            parse_mode='Markdown'
        )
        return TASK_DESCRIPTION
    
    async def add_task_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle task description input"""
        if update.message.text.lower() != 'skip':
            context.user_data['task_description'] = update.message.text
        else:
            context.user_data['task_description'] = ""
        
        await update.message.reply_text(
            "⏰ When is the *deadline*?\n\n"
            "*Examples:*\n"
            "• `2024-12-25 15:30`\n"
            "• `tomorrow at 3pm`\n"
            "• `in 2 hours`\n"
            "• `today at 6pm`",
            parse_mode='Markdown'
        )
        return TASK_DEADLINE
    
    async def add_task_deadline(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle task deadline input"""
        deadline_str = update.message.text
        user_id = update.effective_user.id
        user_timezone = await self.db.get_user_timezone(user_id)
        
        deadline = parse_datetime(deadline_str, user_timezone)
        
        if not deadline:
            await update.message.reply_text(
                "❌ Invalid deadline format. Please try again:\n"
                "Examples: '2024-12-25 15:30', 'tomorrow at 3pm', 'in 2 hours'"
            )
            return TASK_DEADLINE
        
        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
        if deadline <= now_utc:
            await update.message.reply_text(
                "❌ Deadline must be in the future. Please try again:"
            )
            return TASK_DEADLINE
        
        context.user_data['task_deadline'] = deadline
        
        # Create the task
        user_task_id = await self.db.add_task(
            user_id=user_id,
            title=context.user_data['task_title'],
            description=context.user_data['task_description'],
            deadline=deadline
        )
        
        context.user_data['user_task_id'] = user_task_id
        
        # Ask for reminder frequency
        await update.message.reply_text(
            "🔔 *Reminder Settings*\n\n"
            "How often should I remind you?",
            reply_markup=create_frequency_keyboard(),
            parse_mode='Markdown'
        )
        return REMINDER_FREQUENCY
    
    async def handle_frequency_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle frequency selection from inline keyboard"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith('freq_'):
            parts = data.split('_')
            if len(parts) == 3:
                freq_type = parts[1]
                freq_value = int(parts[2])
                
                context.user_data['reminder_frequency_type'] = freq_type
                context.user_data['reminder_frequency_value'] = freq_value
                
                # Ask for active hours
                keyboard = [
                    [
                        InlineKeyboardButton("24/7", callback_data="hours_24_7"),
                        InlineKeyboardButton("Custom Hours", callback_data="hours_custom")
                    ]
                ]
                
                await query.edit_message_text(
                    "⏰ When should reminders be active?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return REMINDER_START_TIME
            elif data == 'freq_custom':
                await query.edit_message_text(
                    "Please enter custom frequency:\n" 
                    "Examples: 'every 45 minutes', 'every 3 hours'"
                )
                return REMINDER_FREQUENCY
        return REMINDER_FREQUENCY
    
    async def handle_custom_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle custom frequency input"""
        freq_result = parse_frequency(update.message.text)
        
        if not freq_result:
            await update.message.reply_text(
                "❌ Invalid frequency format. Please try again:\n"
                "Examples: 'every 45 minutes', 'every 3 hours'"
            )
            return REMINDER_FREQUENCY
        
        context.user_data['reminder_frequency_type'] = freq_result[0]
        context.user_data['reminder_frequency_value'] = freq_result[1]
        
        # Ask for active hours
        keyboard = [
            [
                InlineKeyboardButton("24/7", callback_data="hours_24_7"),
                InlineKeyboardButton("Custom Hours", callback_data="hours_custom")
            ]
        ]
        
        await update.message.reply_text(
            "⏰ When should reminders be active?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return REMINDER_START_TIME
    
    async def handle_hours_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle active hours selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "hours_24_7":
            context.user_data['reminder_start_time'] = None
            context.user_data['reminder_end_time'] = None
            
            # Ask about escalation
            keyboard = [
                [
                    InlineKeyboardButton("Yes", callback_data="escalation_yes"),
                    InlineKeyboardButton("No", callback_data="escalation_no")
                ]
            ]
            
            await query.edit_message_text(
                "📈 Enable escalation?\n\n" 
                "Escalation makes reminders more frequent as the deadline approaches.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return REMINDER_ESCALATION
            
        elif query.data == "hours_custom":
            await query.edit_message_text(
                "Please enter the time when reminders should PAUSE (24-hour format):\n" 
                "Example: 09:00"
            )
            return REMINDER_START_TIME
        return REMINDER_START_TIME
    
    async def handle_start_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle start time input"""
        try:
            time_parts = update.message.text.strip().split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                context.user_data['reminder_start_time'] = f"{hour:02d}:{minute:02d}"
                
                await update.message.reply_text(
                    "Please enter the time when reminders should RESUME (24-hour format):\n"
                    "Example: 22:00"
                )
                return REMINDER_END_TIME
            else:
                raise ValueError
        except:
            await update.message.reply_text(
                "❌ Invalid time format. Please use HH:MM format (e.g., 09:00):"
            )
            return REMINDER_START_TIME
    
    async def handle_end_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle end time input"""
        try:
            time_parts = update.message.text.strip().split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                context.user_data['reminder_end_time'] = f"{hour:02d}:{minute:02d}"
                
                # Ask about escalation
                keyboard = [
                    [
                        InlineKeyboardButton("Yes", callback_data="escalation_yes"),
                        InlineKeyboardButton("No", callback_data="escalation_no")
                    ]
                ]
                
                await update.message.reply_text(
                    "📈 Enable escalation?\n\n"
                    "Escalation makes reminders more frequent as the deadline approaches.",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return REMINDER_ESCALATION
            else:
                raise ValueError
        except:
            await update.message.reply_text(
                "❌ Invalid time format. Please use HH:MM format (e.g., 22:00):"
            )
            return REMINDER_END_TIME
    
    async def handle_escalation_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle escalation selection and finish task creation"""
        query = update.callback_query
        await query.answer()
        
        escalation_enabled = query.data == "escalation_yes"
        
        # Add reminder to database
        user_id = update.effective_user.id
        user_task_id = context.user_data['user_task_id']
        actual_task_id = await self.db.get_actual_task_id(user_id, user_task_id)
        
        await self.db.add_reminder(
            task_id=actual_task_id,
            frequency_type=context.user_data['reminder_frequency_type'],
            frequency_value=context.user_data['reminder_frequency_value'],
            start_time=context.user_data.get('reminder_start_time'),
            end_time=context.user_data.get('reminder_end_time'),
            escalation_enabled=escalation_enabled,
            escalation_threshold=60  # Default 60 minutes
        )
        
        # Schedule reminders
        await self.scheduler.schedule_task_reminders(user_id, user_task_id)
        
        # Send confirmation
        task = await self.db.get_task_by_id(user_id, user_task_id)
        deadline_str = task['deadline'].strftime("%Y-%m-%d %H:%M")
        
        confirmation = f"""
✅ *Task Created Successfully!*

📝 *Title:* {escape_markdown(task['title'])}
📄 *Description:* {escape_markdown(task['description']) if task['description'] else 'None'}
⏰ *Deadline:* {deadline_str}
🔔 *Reminder:* Every {context.user_data['reminder_frequency_value']} {context.user_data['reminder_frequency_type']}
📈 *Escalation:* {'Enabled' if escalation_enabled else 'Disabled'}

Your task ID is: `{user_task_id}`
Use `/done {user_task_id}` to mark it as complete.
Use `/test {user_task_id}` to send a test reminder.
        """
        
        await query.edit_message_text(confirmation, parse_mode='Markdown')
        
        # Clear user data
        context.user_data.clear()
        
        return ConversationHandler.END
    
    @track_activity("list_tasks")
    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all active tasks for the user"""
        user_id = update.effective_user.id
        tasks = await self.db.get_user_tasks(user_id)
        user_timezone = await self.db.get_user_timezone(user_id)
        
        if not tasks:
            await update.message.reply_text(
                "📭 You have no active tasks.\n\n"
                "Use `/add` to create a new task!"
            )
            return
        
        message = format_task_list(tasks, user_timezone)
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def mark_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Mark a task as completed"""
        user_id = update.effective_user.id
        
        # Extract task ID from command
        text = update.message.text
        try:
            if text.startswith('/done'):
                user_task_id = int(text[5:])
            else:
                await update.message.reply_text(
                    "❌ Please specify a task ID.\n"
                    "Example: `/done 5`"
                )
                return
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid task ID format.\n"
                "Example: `/done 5`"
            )
            return
        
        # Get task
        task = await self.db.get_task_by_id(user_id, user_task_id)
        if not task:
            await update.message.reply_text("❌ Task not found.")
            return
        
        if task['user_id'] != user_id:
            await update.message.reply_text("❌ This task doesn't belong to you.")
            return
        
        if task['completed']:
            await update.message.reply_text("ℹ️ This task is already completed.")
            return
        
        # Mark as completed
        await self.db.update_task(
            actual_task_id=task['id'],
            completed=True,
            completed_at=datetime.now()
        )
        
        # Cancel reminders
        await self.scheduler.cancel_task_reminders(task['id'])
        
        await update.message.reply_text(
            f"✅ Task *{escape_markdown(task['title'])}* marked as completed!\n\n"
            "Great job! 🎉",
            parse_mode='Markdown'
        )
    
    async def delete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Delete a task"""
        user_id = update.effective_user.id
        
        # Extract task ID
        text = update.message.text.split()
        if len(text) < 2:
            await update.message.reply_text(
                "❌ Please specify a task ID.\n"
                "Example: `/delete 5`"
            )
            return
        
        try:
            user_task_id = int(text[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid task ID.")
            return
        
        # Get task
        task = await self.db.get_task_by_id(user_id, user_task_id)
        if not task:
            await update.message.reply_text("❌ Task not found.")
            return
        
        if task['user_id'] != user_id:
            await update.message.reply_text("❌ This task doesn't belong to you.")
            return
        
        # Delete task
        await self.db.delete_task(task['id'])
        await self.scheduler.cancel_task_reminders(task['id'])
        
        await update.message.reply_text(
            f"🗑️ Task *{escape_markdown(task['title'])}* has been deleted.",
            parse_mode='Markdown'
        )
    
    async def test_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a test reminder for a task"""
        user_id = update.effective_user.id
        
        # Extract task ID
        text = update.message.text
        try:
            if text.startswith('/test'):
                user_task_id = int(text[5:])
            else:
                await update.message.reply_text(
                    "❌ Please specify a task ID.\n"
                    "Example: `/test 5`"
                )
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid task ID.")
            return
        
        actual_task_id = await self.db.get_actual_task_id(user_id, user_task_id)
        if not actual_task_id:
            await update.message.reply_text("❌ Task not found.")
            return
            
        await self.scheduler.send_test_reminder(user_id, actual_task_id)
    
    async def clear_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Clear all tasks for the user and reset their data"""
        user_id = update.effective_user.id
        
        # Ask for confirmation
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, clear all", callback_data=f"clear_confirm_{user_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="clear_cancel")
            ]
        ]
        
        await update.message.reply_text(
            "⚠️ *Warning!*\n\n"
            "This will delete ALL your tasks and reminders permanently.\n"
            "Are you sure you want to continue?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_clear_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle clear confirmation callback"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("clear_confirm_"):
            user_id = int(query.data.split("_")[2])
            
            # Use the new clear method
            try:
                task_count = await self.db.clear_all_user_data(user_id)
                
                message = f"🗑️ *All Clear!*\n\n"
                message += f"Deleted {task_count} tasks and their reminders.\n"
                message += "Your task list is now empty, and new tasks will start from ID 1.\n\n"
                message += "Use `/add` or `/q` to create new tasks!"
                
                await query.edit_message_text(message, parse_mode='Markdown')
                
            except Exception as e:
                logger.error(f"Error clearing user data: {e}")
                await query.edit_message_text(
                    "❌ An error occurred while clearing your data. Please try again.",
                    parse_mode='Markdown'
                )
            
        else:  # clear_cancel
            await query.edit_message_text(
                "❌ Clear operation cancelled.\n"
                "Your tasks remain unchanged."
            )
    
    @track_activity("quick_add")
    async def quick_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Quick add a task with single command"""
        user_id = update.effective_user.id
        text = update.message.text
        
        # Remove the /q command
        if text.startswith('/q '):
            text = text[3:]
        else:
            await update.message.reply_text(
                "⚡ *Quick Add Format:*\n"
                "`/q <title>, <deadline>, <frequency>`\n\n"
                "*Examples:*\n"
                "• `/q Buy milk, in 2 hours, 30m`\n"
                "• `/q Finish report, tomorrow 5pm, 1h`\n"
                "• `/q Call mom, today 6pm, daily`",
                parse_mode='Markdown'
            )
            return
        
        # Parse the input (split by comma first, fallback to pipe for backward compatibility)
        if ',' in text:
            parts = [p.strip() for p in text.split(',')]
        else:
            parts = [p.strip() for p in text.split('|')]
            
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Invalid format. Use: `/q Title, Deadline, Frequency`\n"
                "Example: `/q Buy groceries, in 2 hours, 30m`",
                parse_mode='Markdown'
            )
            return
        
        title = parts[0]
        deadline_str = parts[1]
        freq_str = parts[2] if len(parts) > 2 else "30m"  # Default frequency
        
        # Validate title
        if not title:
            await update.message.reply_text("❌ Task title cannot be empty.")
            return
        
        # Get user timezone
        user_timezone = await self.db.get_user_timezone(user_id)
        
        # Parse deadline
        deadline = parse_datetime(deadline_str, user_timezone)
        if not deadline:
            await update.message.reply_text(
                "❌ Invalid deadline format.\n"
                "Examples: 'in 2 hours', 'tomorrow 3pm', 'today 6pm'"
            )
            return
        
        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
        if deadline <= now_utc:
            await update.message.reply_text("❌ Deadline must be in the future.")
            return
        
        # Parse frequency with shortcuts
        freq_shortcuts = {
            '15m': ('minutes', 15),
            '30m': ('minutes', 30),
            '45m': ('minutes', 45),
            '1h': ('hours', 1),
            '2h': ('hours', 2),
            '3h': ('hours', 3),
            '4h': ('hours', 4),
            '6h': ('hours', 6),
            '8h': ('hours', 8),
            '12h': ('hours', 12),
            'daily': ('daily', 1),
            'hourly': ('hours', 1)
        }
        
        freq_result = freq_shortcuts.get(freq_str.lower())
        if not freq_result:
            # Try parsing as regular frequency
            freq_result = parse_frequency(freq_str)
            if not freq_result:
                await update.message.reply_text(
                    "❌ Invalid frequency.\n"
                    "Use shortcuts: 15m, 30m, 1h, 2h, daily\n"
                    "Or: 'every 45 minutes', 'every 3 hours'"
                )
                return
        
        freq_type, freq_value = freq_result
        
        # Create the task
        user_task_id = await self.db.add_task(
            user_id=user_id,
            title=title,
            description="",  # Quick add doesn't include description
            deadline=deadline
        )
        
        actual_task_id = await self.db.get_actual_task_id(user_id, user_task_id)
        
        # Add reminder with default settings
        await self.db.add_reminder(
            task_id=actual_task_id,
            frequency_type=freq_type,
            frequency_value=freq_value,
            start_time="08:00",  # Default start time
            end_time="22:00",    # Default end time
            escalation_enabled=True,  # Enable escalation by default
            escalation_threshold=60   # 60 minutes before deadline
        )
        
        # Schedule reminders
        await self.scheduler.schedule_task_reminders(user_id, user_task_id)
        
        # Send confirmation (convert deadline back to user timezone for display)
        try:
            tz = pytz.timezone(user_timezone)
        except:
            tz = pytz.UTC
            
        deadline_local = pytz.UTC.localize(deadline).astimezone(tz)
        deadline_formatted = deadline_local.strftime("%Y-%m-%d %H:%M")
        
        freq_text = f"{freq_value} {freq_type}" if freq_value > 1 else freq_type
        
        confirmation = f"""
⚡ *Quick Task Created!*

📝 *Title:* {escape_markdown(title)}
⏰ *Deadline:* {deadline_formatted}
🔔 *Reminder:* Every {freq_text}
⏱️ *Active Hours:* 8 AM - 10 PM
📈 *Escalation:* Enabled

Task ID: `{user_task_id}`
• Mark complete: `/done {user_task_id}`
• Test reminder: `/test {user_task_id}`
• View all tasks: `/list`
        """
        
        await update.message.reply_text(confirmation, parse_mode='Markdown')
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the current conversation"""
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=None
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors and notify user"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    
    
    def run(self):
        """Start the bot"""
        # Create application with increased timeout
        request = HTTPXRequest(connection_pool_size=8, connect_timeout=20.0, read_timeout=20.0)
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).post_init(self.post_init).post_shutdown(self.post_shutdown).build()
        
        # Add conversation handler for adding tasks
        add_task_conv = ConversationHandler(
            entry_points=[CommandHandler("add", self.add_task_start)],
            states={
                TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_task_title)],
                TASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_task_description)],
                TASK_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_task_deadline)],
                REMINDER_FREQUENCY: [
                    CallbackQueryHandler(self.handle_frequency_callback, pattern="^freq_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_custom_frequency)
                ],
                REMINDER_START_TIME: [
                    CallbackQueryHandler(self.handle_hours_callback, pattern="^hours_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_start_time)
                ],
                REMINDER_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_end_time)],
                REMINDER_ESCALATION: [CallbackQueryHandler(self.handle_escalation_callback, pattern="^escalation_")]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        # Add conversation handler for timezone
        timezone_conv = ConversationHandler(
            entry_points=[CommandHandler("timezone", self.timezone_command)],
            states={
                TIMEZONE_LOCATION: [
                    MessageHandler(filters.LOCATION, self.handle_location),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_manual_timezone),
                    CallbackQueryHandler(self.handle_timezone_callback, pattern="^tz_")
                ]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("q", self.quick_add))  # Quick add handler
        self.application.add_handler(add_task_conv)
        self.application.add_handler(timezone_conv)
        self.application.add_handler(CommandHandler("list", self.list_tasks))
        self.application.add_handler(CommandHandler("done", self.mark_done))
        self.application.add_handler(CommandHandler("delete", self.delete_task))
        self.application.add_handler(CommandHandler("test", self.test_reminder))
        self.application.add_handler(CommandHandler("clear", self.clear_all))
        
        # Add callback handler for clear confirmation
        self.application.add_handler(CallbackQueryHandler(self.handle_clear_callback, pattern="^clear_"))
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        # Start the bot
        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main function"""
    # Start the health check web server in a separate thread
    web_thread = Thread(target=run_health_server, daemon=True)
    web_thread.start()
    logger.info("Started health check web server")
    
    # Start the bot
    bot = ReminderBot()
    bot.run()

if __name__ == '__main__':
    main()
