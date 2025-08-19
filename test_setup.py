#!/usr/bin/env python3
"""
Test script to verify bot setup and configuration
"""
import os
import sys
from datetime import datetime, timedelta

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    try:
        import telegram
        print("✅ python-telegram-bot installed")
    except ImportError:
        print("❌ python-telegram-bot not installed")
        return False
    
    try:
        import dotenv
        print("✅ python-dotenv installed")
    except ImportError:
        print("❌ python-dotenv not installed")
        return False
    
    try:
        import apscheduler
        print("✅ apscheduler installed")
    except ImportError:
        print("❌ apscheduler not installed")
        return False
    
    try:
        import pytz
        print("✅ pytz installed")
    except ImportError:
        print("❌ pytz not installed")
        return False
    
    return True

def test_config():
    """Test configuration"""
    print("\nTesting configuration...")
    
    try:
        from config import TELEGRAM_BOT_TOKEN, DATABASE_NAME
        
        if TELEGRAM_BOT_TOKEN:
            print(f"✅ Bot token found: {TELEGRAM_BOT_TOKEN[:10]}...")
        else:
            print("❌ Bot token not found")
            return False
        
        print(f"✅ Database name: {DATABASE_NAME}")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing config: {e}")
        return False

def test_database():
    """Test database initialization"""
    print("\nTesting database...")
    
    try:
        from database import Database
        from config import DATABASE_NAME
        
        # Create test database
        test_db = Database("test_" + DATABASE_NAME)
        print("✅ Database initialized")
        
        # Test adding a task
        task_id = test_db.add_task(
            user_id=123456789,
            title="Test Task",
            description="This is a test",
            deadline=datetime.now() + timedelta(hours=2)
        )
        print(f"✅ Test task created with ID: {task_id}")
        
        # Test retrieving task
        task = test_db.get_task_by_id(task_id)
        if task:
            print("✅ Task retrieved successfully")
        else:
            print("❌ Failed to retrieve task")
            return False
        
        # Clean up
        test_db.delete_task(task_id)
        print("✅ Test task deleted")
        
        # Remove test database
        import os
        if os.path.exists("test_" + DATABASE_NAME):
            os.remove("test_" + DATABASE_NAME)
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_utils():
    """Test utility functions"""
    print("\nTesting utilities...")
    
    try:
        from utils import parse_datetime, parse_frequency
        
        # Test datetime parsing
        test_cases = [
            ("2024-12-25 15:30", True),
            ("tomorrow at 3pm", True),
            ("in 2 hours", True),
            ("invalid date", False)
        ]
        
        all_passed = True
        for test_input, should_pass in test_cases:
            result = parse_datetime(test_input)
            if (result is not None) == should_pass:
                print(f"✅ parse_datetime('{test_input}'): {'Passed' if result else 'Failed as expected'}")
            else:
                print(f"❌ parse_datetime('{test_input}'): Unexpected result")
                all_passed = False
        
        # Test frequency parsing
        freq_cases = [
            ("every 30 minutes", ('minutes', 30)),
            ("hourly", ('hours', 1)),
            ("daily", ('daily', 1)),
            ("invalid", None)
        ]
        
        for test_input, expected in freq_cases:
            result = parse_frequency(test_input)
            if result == expected:
                print(f"✅ parse_frequency('{test_input}'): {result}")
            else:
                print(f"❌ parse_frequency('{test_input}'): Expected {expected}, got {result}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Utils error: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Nagger Bot Setup Test\n")
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
        ("Utilities", test_utils)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        success = test_func()
        results.append((test_name, success))
    
    print(f"\n{'='*50}")
    print("\n📊 Test Summary:\n")
    
    all_passed = True
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! Your bot is ready to run.")
        print("\nTo start the bot, run:")
        print("  python reminder_bot.py")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues before running the bot.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Check your bot token in .env file")
        sys.exit(1)

if __name__ == "__main__":
    main()
