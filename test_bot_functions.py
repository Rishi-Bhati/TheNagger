#!/usr/bin/env python3
"""
Comprehensive test script for the Nagger Bot functionality
"""
import asyncio
import sqlite3
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database
from models import Task, Reminder, FrequencyType
from utils import parse_datetime, parse_frequency, format_task_list, validate_task_input
from config import DATABASE_NAME

class BotTester:
    def __init__(self):
        self.db = Database("test_" + DATABASE_NAME)
        self.test_user_id = 123456789
        self.results = []
        
    def log_result(self, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append((test_name, success, details))
        print(f"{status} - {test_name}")
        if details:
            print(f"    Details: {details}")
    
    def test_task_creation(self):
        """Test task creation with various inputs"""
        print("\n🧪 Testing Task Creation...")
        
        # Test 1: Basic task creation
        try:
            task_id = self.db.add_task(
                user_id=self.test_user_id,
                title="Test Task 1",
                description="This is a test description",
                deadline=datetime.now() + timedelta(hours=2)
            )
            self.log_result("Basic task creation", task_id > 0, f"Task ID: {task_id}")
        except Exception as e:
            self.log_result("Basic task creation", False, str(e))
        
        # Test 2: Task with empty description
        try:
            task_id = self.db.add_task(
                user_id=self.test_user_id,
                title="Test Task 2",
                description="",
                deadline=datetime.now() + timedelta(days=1)
            )
            self.log_result("Task with empty description", task_id > 0)
        except Exception as e:
            self.log_result("Task with empty description", False, str(e))
        
        # Test 3: Task with long title
        try:
            long_title = "A" * 100  # Max length
            task_id = self.db.add_task(
                user_id=self.test_user_id,
                title=long_title,
                description="Test",
                deadline=datetime.now() + timedelta(hours=1)
            )
            self.log_result("Task with max length title", task_id > 0)
        except Exception as e:
            self.log_result("Task with max length title", False, str(e))
    
    def test_reminder_creation(self):
        """Test reminder creation with various configurations"""
        print("\n🧪 Testing Reminder Creation...")
        
        # Create a task first
        task_id = self.db.add_task(
            user_id=self.test_user_id,
            title="Reminder Test Task",
            description="Testing reminders",
            deadline=datetime.now() + timedelta(hours=4)
        )
        
        # Test 1: Basic reminder (every 30 minutes)
        try:
            reminder_id = self.db.add_reminder(
                task_id=task_id,
                frequency_type="minutes",
                frequency_value=30
            )
            self.log_result("Basic reminder (30 min)", reminder_id > 0)
        except Exception as e:
            self.log_result("Basic reminder (30 min)", False, str(e))
        
        # Test 2: Reminder with custom hours
        try:
            reminder_id = self.db.add_reminder(
                task_id=task_id,
                frequency_type="hours",
                frequency_value=1,
                start_time="09:00",
                end_time="22:00"
            )
            self.log_result("Reminder with custom hours", reminder_id > 0)
        except Exception as e:
            self.log_result("Reminder with custom hours", False, str(e))
        
        # Test 3: Reminder with escalation
        try:
            reminder_id = self.db.add_reminder(
                task_id=task_id,
                frequency_type="minutes",
                frequency_value=60,
                escalation_enabled=True,
                escalation_threshold=120
            )
            self.log_result("Reminder with escalation", reminder_id > 0)
        except Exception as e:
            self.log_result("Reminder with escalation", False, str(e))
        
        # Test 4: Reminder with custom messages
        try:
            custom_messages = [
                "Don't forget about this task!",
                "Hey, this task is still pending!",
                "Seriously, you need to do this!"
            ]
            reminder_id = self.db.add_reminder(
                task_id=task_id,
                frequency_type="minutes",
                frequency_value=15,
                custom_messages=custom_messages
            )
            self.log_result("Reminder with custom messages", reminder_id > 0)
        except Exception as e:
            self.log_result("Reminder with custom messages", False, str(e))
    
    def test_datetime_parsing(self):
        """Test various datetime input formats"""
        print("\n🧪 Testing DateTime Parsing...")
        
        test_cases = [
            ("2024-12-25 15:30", True, "Standard format"),
            ("25/12/2024 15:30", True, "DD/MM/YYYY format"),
            ("in 2 hours", True, "Relative time"),
            ("in 30 minutes", True, "Relative minutes"),
            ("tomorrow at 3pm", True, "Natural language"),
            ("today at 6pm", True, "Today with time"),
            ("invalid date", False, "Invalid format"),
            ("yesterday", False, "Past date"),
        ]
        
        for input_str, should_pass, description in test_cases:
            result = parse_datetime(input_str)
            success = (result is not None) == should_pass
            self.log_result(f"Parse '{input_str}'", success, description)
    
    def test_frequency_parsing(self):
        """Test frequency parsing"""
        print("\n🧪 Testing Frequency Parsing...")
        
        test_cases = [
            ("every 30 minutes", ("minutes", 30)),
            ("every 15 mins", ("minutes", 15)),
            ("hourly", ("hours", 1)),
            ("every 2 hours", ("hours", 2)),
            ("daily", ("daily", 1)),
            ("every hour", ("hours", 1)),
            ("3 times per day", ("hours", 8)),
            ("invalid frequency", None),
        ]
        
        for input_str, expected in test_cases:
            result = parse_frequency(input_str)
            success = result == expected
            self.log_result(f"Parse '{input_str}'", success, f"Got: {result}")
    
    def test_task_operations(self):
        """Test task CRUD operations"""
        print("\n🧪 Testing Task Operations...")
        
        # Create a task
        task_id = self.db.add_task(
            user_id=self.test_user_id,
            title="CRUD Test Task",
            description="Testing CRUD operations",
            deadline=datetime.now() + timedelta(hours=3)
        )
        
        # Test 1: Retrieve task
        task = self.db.get_task_by_id(task_id)
        self.log_result("Retrieve task", task is not None and task['title'] == "CRUD Test Task")
        
        # Test 2: Update task
        success = self.db.update_task(task_id, title="Updated Task Title", description="Updated description")
        updated_task = self.db.get_task_by_id(task_id)
        self.log_result("Update task", success and updated_task['title'] == "Updated Task Title")
        
        # Test 3: Mark as completed
        success = self.db.update_task(task_id, completed=True, completed_at=datetime.now())
        completed_task = self.db.get_task_by_id(task_id)
        self.log_result("Mark task as completed", success and completed_task['completed'] == 1)
        
        # Test 4: List user tasks
        tasks = self.db.get_user_tasks(self.test_user_id)
        self.log_result("List user tasks", len(tasks) > 0)
        
        # Test 5: List only active tasks
        active_tasks = self.db.get_user_tasks(self.test_user_id, include_completed=False)
        completed_count = sum(1 for t in tasks if t['completed'])
        self.log_result("Filter active tasks", len(active_tasks) == len(tasks) - completed_count)
        
        # Test 6: Delete task
        success = self.db.delete_task(task_id)
        deleted_task = self.db.get_task_by_id(task_id)
        self.log_result("Delete task", success and deleted_task is None)
    
    def test_reminder_logic(self):
        """Test reminder scheduling logic"""
        print("\n🧪 Testing Reminder Logic...")
        
        # Create task and reminder
        task_id = self.db.add_task(
            user_id=self.test_user_id,
            title="Reminder Logic Test",
            description="Testing reminder logic",
            deadline=datetime.now() + timedelta(hours=3)
        )
        
        # Test 1: Should send first reminder
        task_data = self.db.get_task_by_id(task_id)
        task = Task(
            id=task_data['id'],
            user_id=task_data['user_id'],
            title=task_data['title'],
            description=task_data['description'],
            deadline=datetime.fromisoformat(task_data['deadline']),
            created_at=datetime.fromisoformat(task_data['created_at']),
            completed=False
        )
        
        reminder = Reminder(
            id=1,
            task_id=task_id,
            frequency_type=FrequencyType.MINUTES,
            frequency_value=30,
            last_sent=None
        )
        
        should_send = reminder.should_send_reminder(task)
        self.log_result("Should send first reminder", should_send)
        
        # Test 2: Should not send if recently sent
        reminder.last_sent = datetime.now() - timedelta(minutes=10)
        should_send = reminder.should_send_reminder(task)
        self.log_result("Should not send if recently sent", not should_send)
        
        # Test 3: Should send after interval
        reminder.last_sent = datetime.now() - timedelta(minutes=35)
        should_send = reminder.should_send_reminder(task)
        self.log_result("Should send after interval", should_send)
        
        # Test 4: Should not send for completed task
        task.completed = True
        should_send = reminder.should_send_reminder(task)
        self.log_result("Should not send for completed task", not should_send)
    
    def test_input_validation(self):
        """Test input validation"""
        print("\n🧪 Testing Input Validation...")
        
        test_cases = [
            ("Valid Task", "Valid description", "tomorrow at 3pm", True, "Valid input"),
            ("", "Description", "tomorrow at 3pm", False, "Empty title"),
            ("A" * 101, "Description", "tomorrow at 3pm", False, "Title too long"),
            ("Task", "A" * 501, "tomorrow at 3pm", False, "Description too long"),
            ("Task", "Description", "invalid date", False, "Invalid date format"),
            ("Task", "Description", "yesterday", False, "Past deadline"),
        ]
        
        for title, desc, deadline, should_pass, description in test_cases:
            is_valid, error = validate_task_input(title, desc, deadline)
            success = is_valid == should_pass
            self.log_result(f"Validate: {description}", success, error if not is_valid else "")
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        print("\n🧪 Testing Edge Cases...")
        
        # Test 1: Non-existent task
        task = self.db.get_task_by_id(99999)
        self.log_result("Get non-existent task", task is None)
        
        # Test 2: Update non-existent task
        success = self.db.update_task(99999, title="New Title")
        self.log_result("Update non-existent task", not success)
        
        # Test 3: Delete non-existent task
        success = self.db.delete_task(99999)
        self.log_result("Delete non-existent task", not success)
        
        # Test 4: Add reminder to non-existent task
        try:
            # This should fail due to foreign key constraint
            reminder_id = self.db.add_reminder(
                task_id=99999,
                frequency_type="minutes",
                frequency_value=30
            )
            self.log_result("Add reminder to non-existent task", False, "Should have failed")
        except:
            self.log_result("Add reminder to non-existent task", True, "Correctly failed")
    
    def run_all_tests(self):
        """Run all tests"""
        print("🔍 Running Comprehensive Bot Tests\n")
        
        self.test_task_creation()
        self.test_reminder_creation()
        self.test_datetime_parsing()
        self.test_frequency_parsing()
        self.test_task_operations()
        self.test_reminder_logic()
        self.test_input_validation()
        self.test_edge_cases()
        
        # Summary
        print("\n" + "="*50)
        print("📊 Test Summary:\n")
        
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All tests passed!")
        else:
            print("\n❌ Some tests failed. Review the output above.")
            print("\nFailed tests:")
            for name, success, details in self.results:
                if not success:
                    print(f"  - {name}: {details}")
        
        # Cleanup
        if os.path.exists("test_" + DATABASE_NAME):
            os.remove("test_" + DATABASE_NAME)

if __name__ == "__main__":
    tester = BotTester()
    tester.run_all_tests()
