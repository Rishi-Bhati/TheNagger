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
from config import DATABASE_NAME, MAX_ESCALATION_FREQUENCY

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
            # Create Task and Reminder objects
            task = Task(
                id=reminder_data['id'],
                user_id=reminder_data['user_id'],
                title=reminder_data['title'],
                description=reminder_data['description'],
                deadline=datetime.fromisoformat(reminder_data['deadline']),
                created_at=datetime.fromisoformat(reminder_data['created_at']),
                completed=bool(reminder_data['completed'])
            )
            
            reminder = Reminder(
                id=reminder_data['id'],  # This might need adjustment based on actual DB schema
                task_id=task.id,
                frequency_type=FrequencyType(reminder_data['frequency_type']),
                frequency_value=reminder_data['frequency_value'],
                start_time=reminder_data.get('start_time'),
                end_time=reminder_data.get('end_time'),
                escalation_enabled=bool(reminder_data.get('escalation_enabled', False)),
                escalation_threshold=reminder_data.get('escalation_threshold', 60),
                custom_messages=reminder_data.get('custom_messages'),
                last_sent=datetime.fromisoformat(reminder_data['last_sent']) if reminder_data.get('last_sent') else None
            )
            
            # Check if reminder should be sent
            if reminder.should_send_reminder(task):
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
            await self.bot.send_message(
                chat_id=task.user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            # Update last sent time
            self.db.update_reminder(
                reminder.id,
                last_sent=datetime.now(),
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
    
    def schedule_task_reminders(self, task_id: int):
        """Schedule reminders for a specific task"""
        try:
            task_data = self.db.get_task_by_id(task_id)
            if not task_data or not task_data['reminders']:
                return
            
            # Remove existing job if any
            if task_id in self.active_jobs:
                self.scheduler.remove_job(self.active_jobs[task_id])
            
            # For now, we rely on the main check_and_send_reminders
            # In a more advanced implementation, we could schedule individual jobs
            
        except Exception as e:
            logger.error(f"Error scheduling reminders for task {task_id}: {e}")
    
    def cancel_task_reminders(self, task_id: int):
        """Cancel reminders for a specific task"""
        if task_id in self.active_jobs:
            try:
                self.scheduler.remove_job(self.active_jobs[task_id])
                del self.active_jobs[task_id]
                logger.info(f"Cancelled reminders for task {task_id}")
            except Exception as e:
                logger.error(f"Error cancelling reminders for task {task_id}: {e}")
    
    async def send_test_reminder(self, user_id: int, task_id: int):
        """Send a test reminder for a task"""
        try:
            task_data = self.db.get_task_by_id(task_id)
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
                user_id=task_data['user_id'],
                title=task_data['title'],
                description=task_data['description'],
                deadline=datetime.fromisoformat(task_data['deadline']),
                created_at=datetime.fromisoformat(task_data['created_at']),
                completed=bool(task_data['completed'])
            )
            
            if task_data['reminders']:
                reminder_data = task_data['reminders'][0]
                reminder = Reminder(
                    id=reminder_data['id'],
                    task_id=task.id,
                    frequency_type=FrequencyType(reminder_data['frequency_type']),
                    frequency_value=reminder_data['frequency_value'],
                    start_time=reminder_data.get('start_time'),
                    end_time=reminder_data.get('end_time'),
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
