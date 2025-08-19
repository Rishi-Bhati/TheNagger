import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Database configuration
DATABASE_NAME = 'reminders.db'

# Timezone configuration
DEFAULT_TIMEZONE = 'UTC'

# Reminder configuration
MAX_REMINDERS_PER_TASK = 100
DEFAULT_REMINDER_INTERVAL = 30  # minutes
MAX_ESCALATION_FREQUENCY = 5  # minutes (minimum interval when escalating)

# Time restrictions
DEFAULT_QUIET_HOURS_START = 22  # 10 PM
DEFAULT_QUIET_HOURS_END = 8     # 8 AM

# Message templates
REMINDER_TEMPLATE = "🔔 *Reminder*: {title}\n\n{description}\n\n⏰ Deadline: {deadline}\n\n_Reply /done{task_id} to mark as complete_"
ESCALATION_TEMPLATE = "🚨 *URGENT REMINDER*: {title}\n\n{description}\n\n⏰ Deadline: {deadline} ({time_left})\n\n_This task is approaching its deadline!_\n_Reply /done{task_id} to mark as complete_"
