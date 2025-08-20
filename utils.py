import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import logging

logger = logging.getLogger(__name__)

def parse_datetime(date_string: str) -> Optional[datetime]:
    """Parse various datetime formats"""
    # Remove extra whitespace
    date_string = date_string.strip()
    
    # Try different formats
    formats = [
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    
    # Try relative time parsing
    relative_time = parse_relative_time(date_string)
    if relative_time:
        return relative_time
    
    return None

def parse_relative_time(time_string: str) -> Optional[datetime]:
    """Parse relative time strings like 'in 2 hours', 'tomorrow at 3pm'"""
    time_string = time_string.lower().strip()
    now = datetime.now()
    
    # Pattern for "in X minutes/hours/days"
    in_pattern = r'in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)'
    match = re.match(in_pattern, time_string)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if 'minute' in unit:
            return now + timedelta(minutes=amount)
        elif 'hour' in unit:
            return now + timedelta(hours=amount)
        elif 'day' in unit:
            return now + timedelta(days=amount)
    
    # Pattern for "tomorrow at HH:MM"
    tomorrow_pattern = r'tomorrow\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?'
    match = re.match(tomorrow_pattern, time_string)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # Pattern for "today at HH:MM"
    today_pattern = r'today\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?'
    match = re.match(today_pattern, time_string)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        
        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If time has passed today, assume tomorrow
        if result <= now:
            result += timedelta(days=1)
        return result
    
    return None

def parse_frequency(frequency_string: str) -> Optional[Tuple[str, int]]:
    """Parse frequency strings like 'every 30 minutes', 'hourly', 'daily'"""
    frequency_string = frequency_string.lower().strip()
    
    # Direct mappings
    if frequency_string in ['hourly', 'every hour']:
        return ('hours', 1)
    elif frequency_string in ['daily', 'every day']:
        return ('daily', 1)
    elif frequency_string in ['every 15 minutes', 'every 15 mins']:
        return ('minutes', 15)
    elif frequency_string in ['every 30 minutes', 'every 30 mins']:
        return ('minutes', 30)
    
    # Pattern for "every X minutes/hours"
    pattern = r'every\s+(\d+)\s+(minute|minutes|min|mins|hour|hours|hr|hrs)'
    match = re.match(pattern, frequency_string)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        
        if unit in ['minute', 'minutes', 'min', 'mins']:
            return ('minutes', value)
        elif unit in ['hour', 'hours', 'hr', 'hrs']:
            return ('hours', value)
    
    # Pattern for "X times per day/hour"
    times_pattern = r'(\d+)\s+times?\s+per\s+(day|hour)'
    match = re.match(times_pattern, frequency_string)
    if match:
        times = int(match.group(1))
        period = match.group(2)
        
        if period == 'day':
            # Convert to hours
            hours = 24 // times
            return ('hours', hours)
        elif period == 'hour':
            # Convert to minutes
            minutes = 60 // times
            return ('minutes', minutes)
    
    return None

def format_task_list(tasks: List[Dict]) -> str:
    """Format task list for display"""
    if not tasks:
        return "📭 No active tasks found."
    
    message = "📋 *Your Active Tasks:*\n\n"
    
    for i, task in enumerate(tasks, 1):
        deadline = task['deadline']
        status = "✅ Completed" if task['completed'] else get_task_status(deadline)
        
        message += f"{i}. *{task['title']}*\n"
        if task['description']:
            message += f"   📝 {task['description']}\n"
        message += f"   ⏰ Deadline: {deadline.strftime('%Y-%m-%d %H:%M')}\n"
        message += f"   📊 Status: {status}\n"
        
        if task['reminders']:
            reminder = task['reminders'][0]  # Show first reminder config
            freq_text = format_frequency(reminder['frequency_type'], reminder['frequency_value'])
            message += f"   🔔 Reminder: {freq_text}\n"
        
        message += f"   🆔 ID: `/done {task['id']}` to complete\n\n"
    
    return message

def get_task_status(deadline: datetime) -> str:
    """Get formatted task status based on deadline"""
    now = datetime.now()
    if deadline < now:
        return "❌ Overdue"
    
    time_left = deadline - now
    days = time_left.days
    hours = time_left.seconds // 3600
    minutes = (time_left.seconds % 3600) // 60
    
    if days > 0:
        return f"⏳ {days}d {hours}h left"
    elif hours > 0:
        return f"⏳ {hours}h {minutes}m left"
    else:
        return f"⏳ {minutes}m left"

def format_frequency(freq_type: str, freq_value: int) -> str:
    """Format frequency for display"""
    if freq_type == 'minutes':
        if freq_value == 1:
            return "Every minute"
        else:
            return f"Every {freq_value} minutes"
    elif freq_type == 'hours':
        if freq_value == 1:
            return "Every hour"
        else:
            return f"Every {freq_value} hours"
    elif freq_type == 'daily':
        return "Daily"
    else:
        return f"Every {freq_value} {freq_type}"

def validate_task_input(title: str, description: str, deadline_str: str) -> Tuple[bool, str]:
    """Validate task input and return (is_valid, error_message)"""
    if not title or len(title.strip()) == 0:
        return False, "Task title cannot be empty."
    
    if len(title) > 100:
        return False, "Task title is too long (max 100 characters)."
    
    if description and len(description) > 500:
        return False, "Task description is too long (max 500 characters)."
    
    deadline = parse_datetime(deadline_str)
    if not deadline:
        return False, "Invalid deadline format. Use formats like '2024-01-20 15:30', 'tomorrow at 3pm', or 'in 2 hours'."
    
    if deadline <= datetime.now():
        return False, "Deadline must be in the future."
    
    return True, ""

def escape_markdown(text: str) -> str:
    """Escape special markdown characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def create_time_selection_keyboard(step: str = 'hour'):
    """Create inline keyboard for time selection"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = []
    
    if step == 'hour':
        # Hour selection (0-23)
        for row in range(6):
            row_buttons = []
            for col in range(4):
                hour = row * 4 + col
                if hour < 24:
                    row_buttons.append(
                        InlineKeyboardButton(f"{hour:02d}:00", callback_data=f"time_hour_{hour}")
                    )
            if row_buttons:
                keyboard.append(row_buttons)
    
    elif step == 'minute':
        # Minute selection (0, 15, 30, 45)
        minutes = [0, 15, 30, 45]
        row_buttons = []
        for minute in minutes:
            row_buttons.append(
                InlineKeyboardButton(f":{minute:02d}", callback_data=f"time_minute_{minute}")
            )
        keyboard.append(row_buttons)
    
    return InlineKeyboardMarkup(keyboard)

def create_frequency_keyboard():
    """Create inline keyboard for frequency selection"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = [
        [
            InlineKeyboardButton("Every 15 mins", callback_data="freq_minutes_15"),
            InlineKeyboardButton("Every 30 mins", callback_data="freq_minutes_30")
        ],
        [
            InlineKeyboardButton("Every hour", callback_data="freq_hours_1"),
            InlineKeyboardButton("Every 2 hours", callback_data="freq_hours_2")
        ],
        [
            InlineKeyboardButton("Every 4 hours", callback_data="freq_hours_4"),
            InlineKeyboardButton("Daily", callback_data="freq_daily_1")
        ],
        [
            InlineKeyboardButton("Custom", callback_data="freq_custom")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)
