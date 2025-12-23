import unittest
from datetime import datetime, timedelta
import pytz
from models import Task, Reminder, FrequencyType

class TestReminderLogic(unittest.TestCase):
    def test_daily_frequency_bug(self):
        # Setup
        now = datetime.now(pytz.UTC)
        deadline = now + timedelta(days=5) # Far future, so no escalation
        
        task = Task(
            id=1, user_task_id=1, user_id=1, 
            title="Test", description="Desc", 
            deadline=deadline, created_at=now
        )
        
        # Last sent 1 hour ago
        last_sent = now - timedelta(hours=1)
        
        reminder = Reminder(
            id=1, task_id=1, 
            frequency_type=FrequencyType.DAILY, frequency_value=1,
            escalation_enabled=True, # This triggers the buggy block
            last_sent=last_sent
        )
        
        # Should be False (1 hour < 1 day)
        # But due to bug, it returns True
        should_send = reminder.should_send_reminder(task, "UTC")
        print(f"Daily test (1 hour since last): {should_send}")
        
        # Assert that it SHOULD be False
        self.assertFalse(should_send, "Daily reminder should not send if only 1 hour passed")

    def test_24_7_logic(self):
        now = datetime.now(pytz.UTC)
        deadline = now + timedelta(days=5)
        
        task = Task(
            id=1, user_task_id=1, user_id=1, 
            title="Test", description="Desc", 
            deadline=deadline, created_at=now
        )
        
        # 24/7 means start/end are None
        reminder = Reminder(
            id=1, task_id=1, 
            frequency_type=FrequencyType.HOURS, frequency_value=1,
            start_time=None, end_time=None,
            last_sent=None
        )
        
        should_send = reminder.should_send_reminder(task, "UTC")
        self.assertTrue(should_send, "24/7 reminder should send")

if __name__ == '__main__':
    unittest.main()
