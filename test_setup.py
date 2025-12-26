#!/usr/bin/env python3
"""
Test script to verify bot setup and configuration (Async version)
"""
import os
import sys
import asyncio
from datetime import datetime, timedelta

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    try:
        import telegram
        print(" [OK] python-telegram-bot installed")
    except ImportError:
        print(" [NO] python-telegram-bot not installed")
        return False
    
    try:
        import dotenv
        print(" [OK] python-dotenv installed")
    except ImportError:
        print(" [NO] python-dotenv not installed")
        return False
    
    try:
        import apscheduler
        print(" [OK] apscheduler installed")
    except ImportError:
        print(" [NO] apscheduler not installed")
        return False
    
    try:
        import pytz
        print(" [OK] pytz installed")
    except ImportError:
        print(" [NO] pytz not installed")
        return False
        
    try:
        import asyncpg
        print(" [OK] asyncpg installed")
    except ImportError:
        print(" [NO] asyncpg not installed")
        return False
    
    return True

def test_config():
    """Test configuration"""
    print("\nTesting configuration...")
    
    try:
        from config import TELEGRAM_BOT_TOKEN
        
        if TELEGRAM_BOT_TOKEN:
            print(f" [OK] Bot token found: {TELEGRAM_BOT_TOKEN[:10]}...")
        else:
            print(" [NO] Bot token not found")
            return False
            
        if os.environ.get("DATABASE_URL"):
             print(" [OK] DATABASE_URL found")
        else:
             print(" [NO] DATABASE_URL environment variable is missing")
             return False

        return True
        
    except ImportError as e:
        print(f" [NO] Error importing config: {e}")
        return False

async def test_database_async():
    """Test database initialization (Async)"""
    print("\nTesting database (Async)...")
    
    try:
        from database import Database
        import os
        
        db = Database()
        await db.connect()
        print(" [OK] Database connected and pool created")
        
        # Test adding a task
        try:
            task_id = await db.add_task(
                user_id=123456789,
                title="Test Task Async",
                description="This is an async test",
                deadline=datetime.now() + timedelta(hours=2)
            )
            print(f" [OK] Test task created with ID: {task_id}")
            
            # Test retrieving task
            task = await db.get_task_by_id(123456789, task_id)
            if task:
                print(" [OK] Task retrieved successfully")
            else:
                print(" [NO] Failed to retrieve task")
                await db.close()
                return False
            
            # Clean up (we need to get actual id to delete)
            actual_id = task['id'] 
            await db.delete_task(actual_id)
            print(" [OK] Test task deleted")
            
        except Exception as e:
            print(f" [NO] Database operation error: {e}")
            await db.close()
            return False
            
        await db.close()
        print(" [OK] Database connection closed")
        
        return True
        
    except Exception as e:
        print(f" [NO] Database error: {e}")
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
                print(f" [OK] parse_datetime('{test_input}'): {'Passed' if result else 'Failed as expected'}")
            else:
                print(f" [NO] parse_datetime('{test_input}'): Unexpected result")
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
                print(f" [OK] parse_frequency('{test_input}'): {result}")
            else:
                print(f" [NO] parse_frequency('{test_input}'): Expected {expected}, got {result}")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f" [NO] Utils error: {e}")
        return False

def main():
    """Run all tests"""
    print(" Nagger Bot Setup Test (Async)\n")
    
    # Sync tests
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Utilities", test_utils)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        success = test_func()
        results.append((test_name, success))
    
    # Async test
    print(f"\n{'='*50}")
    try:
        success = asyncio.run(test_database_async())
        results.append(("Database", success))
    except Exception as e:
        print(f" [NO] Async test runner failed: {e}")
        results.append(("Database", False))

    print(f"\n{'='*50}")
    print("\n Test Summary:\n")
    
    all_passed = True
    for test_name, success in results:
        status = "PASSED" if success else "FAILED"
        print(f"{test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n All tests passed! Your bot is ready to run.")
        print("\nTo start the bot, run:")
        print("  python reminder_bot.py")
    else:
        print("\n [NO] Some tests failed. Please fix the issues before running the bot.")
        sys.exit(1)

if __name__ == "__main__":
    main()
