#!/usr/bin/env python3
import logging
import asyncio
from datetime import datetime, timedelta
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

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
logger = logging.getLogger(__name__)

# Conversation states
TASK_TITLE, TASK_DESCRIPTION, TASK_DEADLINE = range(3)
REMINDER_FREQUENCY, REMINDER_START_TIME, REMINDER_END_TIME, REMINDER_ESCALATION = range(3, 7)
EDIT_CHOICE, EDIT_VALUE = range(7, 9)

class ReminderBot:
    def __init__(self):
        self.db = Database(DATABASE_URL)
        self.application = None
        self.scheduler = None
        
    async def post_init(self, application: Application) -> None:
        """Initialize bot after application is built"""
        self.scheduler = ReminderScheduler(application.bot, self.db)
        await self.scheduler.start()
        logger.info("Bot initialized successfully")
    
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
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a detailed help message"""
        help_text = """
📚 *Nagger Bot Help*

*Commands:*
• `/start` - Start the bot and see welcome message
• `/add` - Add a new task (detailed mode)
• `/q` - Quick add task (single command)
• `/list` - List all active tasks
• `/edit <task_id>` - Edit a task
• `/delete <task_id>` - Delete a task
• `/done <task_id>` - Mark task as completed
• `/test <task_id>` - Send a test reminder
• `/clear` - Clear all your tasks (fresh start)

*Quick Add (NEW!):*
`/q <title> | <deadline> | <frequency>`

Examples:
• `/q Buy milk | in 2 hours | 30m`
• `/q Finish report | tomorrow 5pm | 1h`
• `/q Call mom | today 6pm | 2h`

*Frequency shortcuts:*
• `15m` = every 15 minutes
• `30m` = every 30 minutes  
• `1h` = every hour
• `2h` = every 2 hours
• `daily` = once per day

*Detailed Add:*
Use `/add` for full control over:
• Description
• Custom active hours
• Escalation settings
• Custom messages

*Deadline Formats:*
• Relative: `in 2 hours`, `in 30 minutes`
• Natural: `tomorrow at 3pm`, `today at 6pm`
• Specific: `2024-12-25 15:30`

*Tips:*
• Use `/done <task_id>` (e.g., `/done 5`) for quick completion
• Default reminder hours: 8 AM - 10 PM
• Escalation enabled by default for quick tasks
• Use `/clear` to reset all tasks and start fresh
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    # Task Management Commands
    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the add task conversation"""
        await update.message.reply_text(
            "📝 *Creating a new task*\n\n"
            "Please enter the *task title*:\n"
            "(e.g., 'Finish project report')",
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
        deadline = parse_datetime(deadline_str)
        
        if not deadline:
            await update.message.reply_text(
                "❌ Invalid deadline format. Please try again:\n"
                "Examples: '2024-12-25 15:30', 'tomorrow at 3pm', 'in 2 hours'"
            )
            return TASK_DEADLINE
        
        if deadline <= datetime.now():
            await update.message.reply_text(
                "❌ Deadline must be in the future. Please try again:"
            )
            return TASK_DEADLINE
        
        context.user_data['task_deadline'] = deadline
        
        # Create the task
        user_id = update.effective_user.id
        user_task_id = self.db.add_task(
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
                "Please enter the start time for reminders (24-hour format):\n" 
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
                    "Please enter the end time for reminders (24-hour format):\n"
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
        actual_task_id = self.db.get_actual_task_id(user_id, user_task_id)
        
        self.db.add_reminder(
            task_id=actual_task_id,
            frequency_type=context.user_data['reminder_frequency_type'],
            frequency_value=context.user_data['reminder_frequency_value'],
            start_time=context.user_data.get('reminder_start_time'),
            end_time=context.user_data.get('reminder_end_time'),
            escalation_enabled=escalation_enabled,
            escalation_threshold=60  # Default 60 minutes
        )
        
        # Schedule reminders
        self.scheduler.schedule_task_reminders(user_id, user_task_id)
        
        # Send confirmation
        task = self.db.get_task_by_id(user_id, user_task_id)
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
    
    async def list_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all active tasks for the user"""
        user_id = update.effective_user.id
        tasks = self.db.get_user_tasks(user_id)
        
        if not tasks:
            await update.message.reply_text(
                "📭 You have no active tasks.\n\n"
                "Use `/add` to create a new task!"
            )
            return
        
        message = format_task_list(tasks)
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
                    "Example: `/done5`"
                )
                return
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid task ID format.\n"
                "Example: `/done5`"
            )
            return
        
        # Get task
        task = self.db.get_task_by_id(user_id, user_task_id)
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
        self.db.update_task(
            actual_task_id=task['id'],
            completed=True,
            completed_at=datetime.now()
        )
        
        # Cancel reminders
        self.scheduler.cancel_task_reminders(task['id'])
        
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
        task = self.db.get_task_by_id(user_id, user_task_id)
        if not task:
            await update.message.reply_text("❌ Task not found.")
            return
        
        if task['user_id'] != user_id:
            await update.message.reply_text("❌ This task doesn't belong to you.")
            return
        
        # Delete task
        self.db.delete_task(task['id'])
        self.scheduler.cancel_task_reminders(task['id'])
        
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
                    "Example: `/test5`"
                )
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid task ID.")
            return
        
        actual_task_id = self.db.get_actual_task_id(user_id, user_task_id)
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
                task_count = self.db.clear_all_user_data(user_id)
                
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
                "`/q <title> | <deadline> | <frequency>`\n\n"
                "*Examples:*\n"
                "• `/q Buy milk | in 2 hours | 30m`\n"
                "• `/q Finish report | tomorrow 5pm | 1h`\n"
                "• `/q Call mom | today 6pm | daily`",
                parse_mode='Markdown'
            )
            return
        
        # Parse the input
        parts = [p.strip() for p in text.split('|')]
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ Invalid format. Use: `/q <title> | <deadline> | <frequency>`\n"
                "Example: `/q Buy groceries | in 2 hours | 30m`",
                parse_mode='Markdown'
            )
            return
        
        title, deadline_str, freq_str = parts
        
        # Validate title
        if not title:
            await update.message.reply_text("❌ Task title cannot be empty.")
            return
        
        # Parse deadline
        deadline = parse_datetime(deadline_str)
        if not deadline:
            await update.message.reply_text(
                "❌ Invalid deadline format.\n"
                "Examples: 'in 2 hours', 'tomorrow 3pm', 'today 6pm'"
            )
            return
        
        if deadline <= datetime.now():
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
        user_task_id = self.db.add_task(
            user_id=user_id,
            title=title,
            description="",  # Quick add doesn't include description
            deadline=deadline
        )
        
        actual_task_id = self.db.get_actual_task_id(user_id, user_task_id)
        
        # Add reminder with default settings
        self.db.add_reminder(
            task_id=actual_task_id,
            frequency_type=freq_type,
            frequency_value=freq_value,
            start_time="08:00",  # Default start time
            end_time="22:00",    # Default end time
            escalation_enabled=True,  # Enable escalation by default
            escalation_threshold=60   # 60 minutes before deadline
        )
        
        # Schedule reminders
        self.scheduler.schedule_task_reminders(user_id, user_task_id)
        
        # Send confirmation
        deadline_formatted = deadline.strftime("%Y-%m-%d %H:%M")
        freq_text = f"{freq_value} {freq_type}" if freq_value > 1 else freq_type
        
        confirmation = f"""
⚡ *Quick Task Created!*

📝 *Title:* {escape_markdown(title)}
⏰ *Deadline:* {deadline_formatted}
🔔 *Reminder:* Every {freq_text}
⏱️ *Active Hours:* 8 AM - 10 PM
📈 *Escalation:* Enabled

Task ID: `{user_task_id}`
• Mark complete: `/done{user_task_id}`
• Test reminder: `/test{user_task_id}`
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
        # Create application
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(self.post_init).build()
        
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
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("q", self.quick_add))  # Quick add handler
        self.application.add_handler(add_task_conv)
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
