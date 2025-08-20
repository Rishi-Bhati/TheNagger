from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from enum import Enum

class FrequencyType(Enum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAILY = "daily"
    SPECIFIC_TIMES = "specific_times"
    CUSTOM = "custom"

@dataclass
class Task:
    id: int
    user_task_id: int
    user_id: int
    title: str
    description: str
    deadline: datetime
    created_at: datetime
    completed: bool = False
    completed_at: Optional[datetime] = None
    reminders: List['Reminder'] = None
    
    def __post_init__(self):
        if self.reminders is None:
            self.reminders = []
    
    def is_overdue(self) -> bool:
        """Check if task is past deadline"""
        return datetime.now() > self.deadline and not self.completed
    
    def time_until_deadline(self) -> timedelta:
        """Get time remaining until deadline"""
        return self.deadline - datetime.now()
    
    def get_status(self) -> str:
        """Get task status string"""
        if self.completed:
            return "✅ Completed"
        elif self.is_overdue():
            return "❌ Overdue"
        else:
            time_left = self.time_until_deadline()
            days = time_left.days
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            
            if days > 0:
                return f"⏳ {days}d {hours}h left"
            elif hours > 0:
                return f"⏳ {hours}h {minutes}m left"
            else:
                return f"⏳ {minutes}m left"
    
    def to_dict(self) -> Dict:
        """Convert task to dictionary"""
        return {
            'id': self.id,
            'user_task_id': self.user_task_id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'deadline': self.deadline.isoformat(),
            'created_at': self.created_at.isoformat(),
            'completed': self.completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'reminders': [r.to_dict() for r in self.reminders] if self.reminders else []
        }

@dataclass
class Reminder:
    id: int
    task_id: int
    frequency_type: FrequencyType
    frequency_value: int
    start_time: Optional[str] = None  # HH:MM format
    end_time: Optional[str] = None    # HH:MM format
    escalation_enabled: bool = False
    escalation_threshold: int = 60    # minutes before deadline to start escalating
    custom_messages: Optional[List[str]] = None
    last_sent: Optional[datetime] = None
    next_reminder: Optional[datetime] = None
    
    def should_send_reminder(self, task: Task) -> bool:
        """Check if reminder should be sent now"""
        if task.completed or task.is_overdue():
            return False
        
        now = datetime.now()
        
        # Check if within active hours
        if self.start_time and self.end_time:
            current_time = now.strftime("%H:%M")
            if not self._is_within_active_hours(current_time):
                return False
        
        # Check if enough time has passed since last reminder
        if self.last_sent:
            time_since_last = now - self.last_sent
            
            # Check escalation
            if self.escalation_enabled:
                time_until_deadline = task.time_until_deadline()
                if time_until_deadline.total_seconds() / 60 <= self.escalation_threshold:
                    # Escalate frequency
                    escalated_interval = max(5, self.frequency_value // 2)  # Minimum 5 minutes
                    if time_since_last.total_seconds() / 60 < escalated_interval:
                        return False
                else:
                    # Normal frequency
                    if self.frequency_type == FrequencyType.MINUTES:
                        if time_since_last.total_seconds() / 60 < self.frequency_value:
                            return False
                    elif self.frequency_type == FrequencyType.HOURS:
                        if time_since_last.total_seconds() / 3600 < self.frequency_value:
                            return False
            else:
                # Normal frequency check
                if self.frequency_type == FrequencyType.MINUTES:
                    if time_since_last.total_seconds() / 60 < self.frequency_value:
                        return False
                elif self.frequency_type == FrequencyType.HOURS:
                    if time_since_last.total_seconds() / 3600 < self.frequency_value:
                        return False
                elif self.frequency_type == FrequencyType.DAILY:
                    if time_since_last.days < 1:
                        return False
        
        return True
    
    def _is_within_active_hours(self, current_time: str) -> bool:
        """Check if current time is within active hours"""
        # Handle both string and datetime.time objects for start_time and end_time
        if hasattr(self.start_time, 'hour'):
            # It's a datetime.time object
            start_hour, start_min = self.start_time.hour, self.start_time.minute
        else:
            # It's a string
            start_hour, start_min = map(int, self.start_time.split(':'))
        
        if hasattr(self.end_time, 'hour'):
            # It's a datetime.time object
            end_hour, end_min = self.end_time.hour, self.end_time.minute
        else:
            # It's a string
            end_hour, end_min = map(int, self.end_time.split(':'))
        
        curr_hour, curr_min = map(int, current_time.split(':'))
        
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        curr_minutes = curr_hour * 60 + curr_min
        
        if start_minutes <= end_minutes:
            return start_minutes <= curr_minutes <= end_minutes
        else:  # Overnight range
            return curr_minutes >= start_minutes or curr_minutes <= end_minutes
    
    def get_next_reminder_time(self) -> datetime:
        """Calculate next reminder time"""
        if not self.last_sent:
            return datetime.now()
        
        if self.frequency_type == FrequencyType.MINUTES:
            return self.last_sent + timedelta(minutes=self.frequency_value)
        elif self.frequency_type == FrequencyType.HOURS:
            return self.last_sent + timedelta(hours=self.frequency_value)
        elif self.frequency_type == FrequencyType.DAILY:
            return self.last_sent + timedelta(days=1)
        else:
            return self.last_sent + timedelta(minutes=self.frequency_value)
    
    def get_reminder_message(self, task: Task, is_escalated: bool = False) -> str:
        """Get the reminder message to send"""
        if is_escalated:
            from config import ESCALATION_TEMPLATE
            time_left = task.time_until_deadline()
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            time_left_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            return ESCALATION_TEMPLATE.format(
                title=task.title,
                description=task.description,
                deadline=task.deadline.strftime("%Y-%m-%d %H:%M"),
                time_left=time_left_str,
                task_id=task.id
            )
        else:
            from config import REMINDER_TEMPLATE
            # Use custom message if available
            if self.custom_messages and len(self.custom_messages) > 0:
                # Cycle through custom messages
                message_index = 0
                if self.last_sent:
                    # Simple cycling through messages
                    message_index = hash(str(self.last_sent)) % len(self.custom_messages)
                
                custom_text = self.custom_messages[message_index]
                return f"🔔 *Reminder*: {task.title}\n\n{custom_text}\n\n⏰ Deadline: {task.deadline.strftime('%Y-%m-%d %H:%M')}\n\n_Reply /done {task.id} to mark as complete_"
            else:
                return REMINDER_TEMPLATE.format(
                    title=task.title,
                    description=task.description,
                    deadline=task.deadline.strftime("%Y-%m-%d %H:%M"),
                    task_id=task.id
                )
    
    def to_dict(self) -> Dict:
        """Convert reminder to dictionary"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'frequency_type': self.frequency_type.value,
            'frequency_value': self.frequency_value,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'escalation_enabled': self.escalation_enabled,
            'escalation_threshold': self.escalation_threshold,
            'custom_messages': self.custom_messages,
            'last_sent': self.last_sent.isoformat() if self.last_sent else None,
            'next_reminder': self.next_reminder.isoformat() if self.next_reminder else None
        }
