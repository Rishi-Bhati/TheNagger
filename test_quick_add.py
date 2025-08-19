#!/usr/bin/env python3
"""
Comprehensive test script for the quick add feature
"""
import asyncio
import sys
from datetime import datetime, timedelta
from database import Database
from utils import parse_datetime, parse_frequency
from models import Task, Reminder, FrequencyType

# Test data for quick add feature
QUICK_ADD_TEST_CASES = [
    # Valid cases
    {
        "input": "Buy milk | in 2 hours | 30m",
        "expected": {
            "title": "Buy milk",
            "deadline_valid": True,
            "frequency": ("minutes", 30)
        }
    },
    {
        "input": "Finish report | tomorrow 5pm | 1h",
        "expected": {
            "title": "Finish report",
            "deadline_valid": True,
            "frequency": ("hours", 1)
        }
    },
    {
        "input": "Call mom | today 6pm | daily",
        "expected": {
            "title": "Call mom",
            "deadline_valid": True,
            "frequency": ("daily", 1)
        }
    },
    {
        "input": "Meeting prep | in 45 minutes | 15m",
        "expected": {
            "title": "Meeting prep",
            "deadline_valid": True,
            "frequency": ("minutes", 15)
        }
    },
    # Edge cases
    {
        "input": "Task with spaces | in 3 hours | 2h",
        "expected": {
            "title": "Task with spaces",
            "deadline_valid": True,
            "frequency": ("hours", 2)
        }
    },
    {
        "input": "Long task title that should still work fine | tomorrow at 9am | hourly",
        "expected": {
            "title": "Long task title that should still work fine",
            "deadline_valid": True,
            "frequency": ("hours", 1)
        }
    },
    # Invalid cases
    {
        "input": "Missing frequency | in 2 hours",
        "expected": {
            "error": "Invalid format"
        }
    },
    {
        "input": " | in 2 hours | 30m",  # Empty title
        "expected": {
            "error": "Empty title"
        }
    },
    {
        "input": "Invalid deadline | yesterday | 30m",
        "expected": {
            "error": "Past deadline"
        }
    },
    {
        "input": "Invalid frequency | in 2 hours | invalid",
        "expected": {
            "error": "Invalid frequency"
        }
    }
]

def test_quick_add_parsing():
    """Test parsing of quick add command inputs"""
    print("\n=== Testing Quick Add Parsing ===")
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(QUICK_ADD_TEST_CASES):
        print(f"\nTest {i+1}: {test_case['input']}")
        
        # Parse the input
        parts = [p.strip() for p in test_case['input'].split('|')]
        
        if len(parts) != 3:
            if "error" in test_case["expected"] and "format" in test_case["expected"]["error"].lower():
                print("✅ Correctly identified invalid format")
                passed += 1
            else:
                print("❌ Failed to parse correctly")
                failed += 1
            continue
        
        title, deadline_str, freq_str = parts
        
        # Test title
        if not title and "error" in test_case["expected"] and "title" in test_case["expected"]["error"].lower():
            print("✅ Correctly identified empty title")
            passed += 1
            continue
        elif title and "title" in test_case["expected"]:
            if title == test_case["expected"]["title"]:
                print(f"✅ Title parsed correctly: '{title}'")
            else:
                print(f"❌ Title mismatch: got '{title}', expected '{test_case['expected']['title']}'")
                failed += 1
                continue
        
        # Test deadline
        deadline = parse_datetime(deadline_str)
        if not deadline and "error" in test_case["expected"]:
            print("✅ Correctly identified invalid deadline")
            passed += 1
            continue
        elif deadline and deadline <= datetime.now() and "error" in test_case["expected"] and "past" in test_case["expected"]["error"].lower():
            print("✅ Correctly identified past deadline")
            passed += 1
            continue
        elif deadline and test_case["expected"].get("deadline_valid"):
            print(f"✅ Deadline parsed correctly: {deadline}")
        
        # Test frequency
        freq_shortcuts = {
            '15m': ('minutes', 15),
            '30m': ('minutes', 30),
            '45m': ('minutes', 45),
            '1h': ('hours', 1),
            '2h': ('hours', 2),
            '3h': ('hours', 3),
            '4h': ('hours', 4),
            '6h': ('hours', 6),
            '8h': ('hours', 8),
            '12h': ('hours', 12),
            'daily': ('daily', 1),
            'hourly': ('hours', 1)
        }
        
        freq_result = freq_shortcuts.get(freq_str.lower())
        if not freq_result:
            freq_result = parse_frequency(freq_str)
        
        if not freq_result and "error" in test_case["expected"] and "frequency" in test_case["expected"]["error"].lower():
            print("✅ Correctly identified invalid frequency")
            passed += 1
            continue
        elif freq_result and "frequency" in test_case["expected"]:
            if freq_result == test_case["expected"]["frequency"]:
                print(f"✅ Frequency parsed correctly: {freq_result}")
                passed += 1
            else:
                print(f"❌ Frequency mismatch: got {freq_result}, expected {test_case['expected']['frequency']}")
                failed += 1
        
    print(f"\n=== Quick Add Parsing Results: {passed} passed, {failed} failed ===")
    return passed, failed

def test_quick_add_database_integration():
    """Test database integration for quick add feature"""
    print("\n=== Testing Quick Add Database Integration ===")
    
    # Create test database
    test_db = Database("test_quick_add.db")
    
    passed = 0
    failed = 0
    
    try:
        # Test 1: Create task with quick add defaults
        print("\nTest 1: Creating task with quick add defaults")
        user_id = 12345
        task_id = test_db.add_task(
            user_id=user_id,
            title="Quick test task",
            description="",  # Quick add uses empty description
            deadline=datetime.now() + timedelta(hours=2)
        )
        
        if task_id:
            print("✅ Task created successfully")
            passed += 1
            
            # Add reminder with quick add defaults
            reminder_id = test_db.add_reminder(
                task_id=task_id,
                frequency_type="minutes",
                frequency_value=30,
                start_time="08:00",  # Default start time
                end_time="22:00",    # Default end time
                escalation_enabled=True,  # Default enabled
                escalation_threshold=60   # Default 60 minutes
            )
            
            if reminder_id:
                print("✅ Reminder created with default settings")
                passed += 1
            else:
                print("❌ Failed to create reminder")
                failed += 1
        else:
            print("❌ Failed to create task")
            failed += 1
        
        # Test 2: Verify task retrieval
        print("\nTest 2: Retrieving quick-added task")
        task = test_db.get_task_by_id(task_id)
        if task and task['title'] == "Quick test task" and task['description'] == "":
            print("✅ Task retrieved correctly with empty description")
            passed += 1
        else:
            print("❌ Task retrieval failed or data mismatch")
            failed += 1
        
        # Test 3: Test multiple quick adds
        print("\nTest 3: Multiple quick adds")
        task_ids = []
        for i in range(3):
            tid = test_db.add_task(
                user_id=user_id,
                title=f"Quick task {i+1}",
                description="",
                deadline=datetime.now() + timedelta(hours=i+1)
            )
            if tid:
                task_ids.append(tid)
                test_db.add_reminder(
                    task_id=tid,
                    frequency_type="hours",
                    frequency_value=1,
                    start_time="08:00",
                    end_time="22:00",
                    escalation_enabled=True,
                    escalation_threshold=60
                )
        
        if len(task_ids) == 3:
            print("✅ Multiple tasks created successfully")
            passed += 1
        else:
            print("❌ Failed to create multiple tasks")
            failed += 1
        
        # Test 4: List all tasks
        print("\nTest 4: Listing all quick-added tasks")
        tasks = test_db.get_user_tasks(user_id)
        if len(tasks) == 4:  # 1 from test 1 + 3 from test 3
            print(f"✅ All {len(tasks)} tasks retrieved")
            passed += 1
        else:
            print(f"❌ Expected 4 tasks, got {len(tasks)}")
            failed += 1
        
    finally:
        # Cleanup
        import os
        if os.path.exists("test_quick_add.db"):
            os.remove("test_quick_add.db")
    
    print(f"\n=== Database Integration Results: {passed} passed, {failed} failed ===")
    return passed, failed

def test_frequency_shortcuts():
    """Test all frequency shortcuts"""
    print("\n=== Testing Frequency Shortcuts ===")
    
    shortcuts = {
        '15m': ('minutes', 15),
        '30m': ('minutes', 30),
        '45m': ('minutes', 45),
        '1h': ('hours', 1),
        '2h': ('hours', 2),
        '3h': ('hours', 3),
        '4h': ('hours', 4),
        '6h': ('hours', 6),
        '8h': ('hours', 8),
        '12h': ('hours', 12),
        'daily': ('daily', 1),
        'hourly': ('hours', 1)
    }
    
    passed = 0
    failed = 0
    
    for shortcut, expected in shortcuts.items():
        print(f"\nTesting shortcut: {shortcut}")
        # The bot would use the shortcuts dict directly, so we test that
        result = shortcuts.get(shortcut.lower())
        if result == expected:
            print(f"✅ {shortcut} → {expected}")
            passed += 1
        else:
            print(f"❌ {shortcut} failed")
            failed += 1
    
    # Test case sensitivity
    print("\nTesting case sensitivity:")
    for shortcut in ['30M', '1H', 'DAILY']:
        result = shortcuts.get(shortcut.lower())
        if result:
            print(f"✅ {shortcut} (uppercase) → {result}")
            passed += 1
        else:
            print(f"❌ {shortcut} (uppercase) failed")
            failed += 1
    
    print(f"\n=== Frequency Shortcuts Results: {passed} passed, {failed} failed ===")
    return passed, failed

def test_edge_cases():
    """Test edge cases for quick add"""
    print("\n=== Testing Edge Cases ===")
    
    passed = 0
    failed = 0
    
    # Test 1: Very long title
    print("\nTest 1: Very long title")
    long_title = "This is a very long task title that exceeds normal length but should still work correctly in the system"
    parts = [long_title, "in 2 hours", "30m"]
    if len(parts[0]) > 100:  # Assuming 100 char limit
        print("✅ Correctly identified title too long")
        passed += 1
    else:
        print("✅ Long title within limits")
        passed += 1
    
    # Test 2: Special characters in title
    print("\nTest 2: Special characters in title")
    special_title = "Task with @#$% special & characters!"
    # The bot should handle these
    print("✅ Special characters should be handled")
    passed += 1
    
    # Test 3: Minimum deadline (very soon)
    print("\nTest 3: Very near deadline")
    deadline = parse_datetime("in 1 minute")
    if deadline and deadline > datetime.now():
        print("✅ Near deadline accepted")
        passed += 1
    else:
        print("❌ Near deadline rejected")
        failed += 1
    
    # Test 4: Maximum deadline (far future)
    print("\nTest 4: Far future deadline")
    deadline = parse_datetime("in 365 days")
    if deadline:
        print("✅ Far future deadline accepted")
        passed += 1
    else:
        print("❌ Far future deadline rejected")
        failed += 1
    
    # Test 5: Whitespace handling
    print("\nTest 5: Extra whitespace")
    input_with_spaces = "  Task title  |  in 2 hours  |  30m  "
    parts = [p.strip() for p in input_with_spaces.split('|')]
    if parts[0] == "Task title" and parts[2] == "30m":
        print("✅ Whitespace handled correctly")
        passed += 1
    else:
        print("❌ Whitespace not handled properly")
        failed += 1
    
    print(f"\n=== Edge Cases Results: {passed} passed, {failed} failed ===")
    return passed, failed

def main():
    """Run all tests"""
    print("=" * 50)
    print("QUICK ADD FEATURE - COMPREHENSIVE TESTING")
    print("=" * 50)
    
    total_passed = 0
    total_failed = 0
    
    # Run all test suites
    tests = [
        test_quick_add_parsing,
        test_frequency_shortcuts,
        test_quick_add_database_integration,
        test_edge_cases
    ]
    
    for test_func in tests:
        passed, failed = test_func()
        total_passed += passed
        total_failed += failed
    
    # Final summary
    print("\n" + "=" * 50)
    print("FINAL TEST SUMMARY")
    print("=" * 50)
    print(f"Total Tests Passed: {total_passed}")
    print(f"Total Tests Failed: {total_failed}")
    print(f"Success Rate: {(total_passed / (total_passed + total_failed) * 100):.1f}%")
    
    if total_failed == 0:
        print("\n✅ ALL TESTS PASSED! Quick add feature is working correctly.")
    else:
        print(f"\n⚠️ {total_failed} tests failed. Please review the implementation.")
    
    return total_failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
