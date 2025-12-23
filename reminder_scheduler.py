import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from telegram.error import TelegramError

from database import Database
from models import Task, Reminder, FrequencyType
from config import MAX_ESCALATION_FREQUENCY

logger = logging.getLogger(__name__)

class ReminderScheduler:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.scheduler = AsyncIOScheduler()
        self.active_jobs = {}  # task_id -> job_id mapping
        
    async def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        # Schedule the main check every minute
        self.scheduler.add_job(
            self.check_and_send_reminders,
            IntervalTrigger(minutes=1),
            id='main_reminder_check',
            replace_existing=True
        )
        logger.info("Reminder scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Reminder scheduler stopped")
    
    async def check_and_send_reminders(self):
        """Main function to check and send due reminders"""
        try:
            # Get all pending reminders
            pending_reminders = self.db.get_pending_reminders()
            
            for reminder_data in pending_reminders:
                await self._process_reminder(reminder_data)
                
        except Exception as e:
            logger.error(f"Error in reminder check: {e}")
    
    async def _process_reminder(self, reminder_data: Dict):
        """Process a single reminder"""
        try:
            # Handle datetime fields - PostgreSQL returns datetime objects directly
            deadline = reminder_data['deadline']
            if isinstance(deadline, str):
                deadline = datetime.fromisoformat(deadline)
            
            created_at = reminder_data['created_at']
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            last_sent = reminder_data.get('last_sent')
            if last_sent and isinstance(last_sent, str):
                last_sent = datetime.fromisoformat(last_sent)
            
            # Handle time fields - PostgreSQL returns time objects
            start_time = reminder_data.get('start_time')
            end_time = reminder_data.get('end_time')
            
            # Convert datetime.time objects to string format "HH:MM"
            if start_time and hasattr(start_time, 'strftime'):
                start_time = start_time.strftime('%H:%M')
            if end_time and hasattr(end_time, 'strftime'):
                end_time = end_time.strftime('%H:%M')
            
            # Create Task and Reminder objects
            task = Task(
                id=reminder_data['task_id'],
                user_task_id=reminder_data.get('user_task_id', reminder_data['task_id']), # Fallback for safety
                user_id=reminder_data['user_id'],
                title=reminder_data['title'],
                description=reminder_data['description'],
                deadline=deadline,
                created_at=created_at,
                completed=bool(reminder_data['completed'])
            )
            
            reminder = Reminder(
                id=reminder_data['reminder_id'],
                task_id=reminder_data['task_id'],
                frequency_type=FrequencyType(reminder_data['frequency_type']),
                frequency_value=reminder_data['frequency_value'],
                start_time=start_time,
                end_time=end_time,
                escalation_enabled=bool(reminder_data.get('escalation_enabled', False)),
                escalation_threshold=reminder_data.get('escalation_threshold', 60),
                custom_messages=reminder_data.get('custom_messages'),
                last_sent=last_sent
            )
            
            # Get user timezone
            user_timezone = self.db.get_user_timezone(reminder_data['user_id'])
            
            # Check if reminder should be sent
            if reminder.should_send_reminder(task, user_timezone):
                await self._send_reminder(task, reminder)
                
        except Exception as e:
            logger.error(f"Error processing reminder for task {reminder_data.get('id')}: {e}")
    
    async def _send_reminder(self, task: Task, reminder: Reminder):
        """Send a reminder message"""
        try:
            # Check if escalation is needed
            is_escalated = False
            if reminder.escalation_enabled:
                time_until_deadline = task.time_until_deadline()
                if time_until_deadline.total_seconds() / 60 <= reminder.escalation_threshold:
                    is_escalated = True
            
            # Get the reminder message
            message = reminder.get_reminder_message(task, is_escalated)
            
            # Send the message
            try:
                await self.bot.send_message(
                    chat_id=task.user_id,
                    text=message,
                    parse_mode='Markdown'
                )
            except TelegramError as e:
                if "Chat not found" in e.message:
                    logger.warning(f"Chat not found for user {task.user_id}. The user may have blocked the bot.")
                    # Optionally, you could add logic here to disable reminders for this user.
                else:
                    raise e
            
            # Update last sent time
            import pytz
            self.db.update_reminder(
                reminder.id,
                last_sent=datetime.now(pytz.UTC),
                next_reminder=reminder.get_next_reminder_time()
            )
            
            # Log the reminder
            self.db.log_reminder_sent(
                task.id,
                'escalated' if is_escalated else 'normal'
            )
            
            logger.info(f"Sent {'escalated' if is_escalated else 'normal'} reminder for task {task.id} to user {task.user_id}")
            
        except TelegramError as e:
            logger.error(f"Failed to send reminder to user {task.user_id}: {e}")
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
    
    def schedule_task_reminders(self, user_id: int, user_task_id: int):
        """Schedule reminders for a specific task"""
        logger.info(f"Scheduling reminders for user {user_id}, task {user_task_id}")
        try:
            task_data = self.db.get_task_by_id(user_id, user_task_id)
            if not task_data or not task_data['reminders']:
                return
            
            actual_task_id = task_data['id']
            
            # Remove existing job if any
            if actual_task_id in self.active_jobs:
                self.scheduler.remove_job(self.active_jobs[actual_task_id])
            
            # For now, we rely on the main check_and_send_reminders
            # In a more advanced implementation, we could schedule individual jobs
            
            logger.info(f"Successfully scheduled reminders for user {user_id}, task {user_task_id}")
        except Exception as e:
            logger.error(f"Error scheduling reminders for task {user_task_id}: {e}")
    
    def cancel_task_reminders(self, task_id: int):
        """Cancel reminders for a specific task"""
        if task_id in self.active_jobs:
            try:
                self.scheduler.remove_job(self.active_jobs[task_id])
                del self.active_jobs[task_id]
                logger.info(f"Cancelled reminders for task {task_id}")
            except Exception as e:
                logger.error(f"Error cancelling reminders for task {task_id}: {e}")
    
    async def send_test_reminder(self, user_id: int, user_task_id: int):
        """Send a test reminder for a task"""
        try:
            task_data = self.db.get_task_by_id(user_id, user_task_id)
            if not task_data:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="❌ Task not found."
                )
                return
            
            if task_data['user_id'] != user_id:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="❌ You don't have permission to test this task."
                )
                return
            
            # Create task object
            task = Task(
                id=task_data['id'],
                user_task_id=task_data.get('user_task_id', task_data['id']), # Fallback for safety
                user_id=task_data['user_id'],
                title=task_data['title'],
                description=task_data['description'],
                deadline=task_data['deadline'],
                created_at=task_data['created_at'],
                completed=bool(task_data['completed'])
            )
            
            if task_data['reminders']:
                reminder_data = task_data['reminders'][0]
                
                # Handle time fields - PostgreSQL returns time objects
                start_time = reminder_data.get('start_time')
                end_time = reminder_data.get('end_time')
                
                # Convert datetime.time objects to string format "HH:MM"
                if start_time and hasattr(start_time, 'strftime'):
                    start_time = start_time.strftime('%H:%M')
                if end_time and hasattr(end_time, 'strftime'):
                    end_time = end_time.strftime('%H:%M')
                
                reminder = Reminder(
                    id=reminder_data['id'],
                    task_id=task.id,
                    frequency_type=FrequencyType(reminder_data['frequency_type']),
                    frequency_value=reminder_data['frequency_value'],
                    start_time=start_time,
                    end_time=end_time,
                    escalation_enabled=bool(reminder_data.get('escalation_enabled', False)),
                    escalation_threshold=reminder_data.get('escalation_threshold', 60),
                    custom_messages=reminder_data.get('custom_messages')
                )
                
                # Send test reminder
                message = reminder.get_reminder_message(task, False)
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"🧪 *Test Reminder*\n\n{message}",
                    parse_mode='Markdown'
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text="❌ No reminders configured for this task."
                )
                
        except Exception as e:
            logger.error(f"Error sending test reminder: {e}")
            await self.bot.send_message(
                chat_id=user_id,
                text="❌ Error sending test reminder."
            )
    
    def get_scheduler_info(self) -> Dict:
        """Get information about the scheduler status"""
        jobs = self.scheduler.get_jobs()
        return {
            'running': self.scheduler.running,
            'jobs_count': len(jobs),
            'active_tasks': len(self.active_jobs),
            'next_run': min([job.next_run_time for job in jobs]) if jobs else None
        }
