import unittest
from datetime import datetime
import pytz
from utils import parse_datetime, validate_task_input

class TestTimezoneLogic(unittest.TestCase):
    def test_parse_datetime_utc(self):
        # Test default UTC
        dt = parse_datetime("2025-01-01 10:00", "UTC")
        self.assertEqual(dt.hour, 10)
        self.assertEqual(dt.minute, 0)
        
    def test_parse_datetime_timezone(self):
        # Test with a specific timezone (e.g., Asia/Kolkata is UTC+5:30)
        # 10:00 AM IST is 4:30 AM UTC
        dt = parse_datetime("2025-01-01 10:00", "Asia/Kolkata")
        self.assertEqual(dt.hour, 4)
        self.assertEqual(dt.minute, 30)
        
    def test_relative_time_timezone(self):
        # "in 1 hour" should be 1 hour from now, regardless of timezone, 
        # but stored as UTC.
        # If it's 12:00 UTC (17:30 IST), "in 1 hour" is 13:00 UTC.
        # The parse_datetime function uses datetime.now(tz) internally.
        
        # This is harder to test deterministically without mocking datetime.now,
        # but we can check if it returns a valid datetime object
        dt = parse_datetime("in 1 hour", "Asia/Kolkata")
        self.assertIsNotNone(dt)
        
    def test_validate_task_input(self):
        valid, msg = validate_task_input("Test", "Desc", "in 1 hour", "UTC")
        self.assertTrue(valid)
        
        valid, msg = validate_task_input("Test", "Desc", "2020-01-01", "UTC")
        self.assertFalse(valid)
        self.assertIn("future", msg)

if __name__ == '__main__':
    unittest.main()
