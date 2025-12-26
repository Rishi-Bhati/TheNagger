# Release Notes

## v1.0.0 - The Birth of the Nagger 
*Release Date: August 19, 2025*

The initial release of Nagger Bot, designed to annoy you into productivity.

### Features
*   **Basic Task Management**: Add, list, and delete tasks.
*   **Quick Add (`/q`)**: Fast task entry using pipe separators (e.g., `/q Buy milk | 5pm | 30m`).
*   **Reminders**:
    *   Set frequency in minutes, hours, or daily.
    *   **Active Hours**: Reminders only send between 8 AM and 10 PM.
    *   **Escalation**: Reminders get more frequent as the deadline approaches.
*   **Commands**:
    *   `/start`: Welcome message.
    *   `/add`: Interactive task creation.
    *   `/list`: View active tasks.
    *   `/done <id>`: Mark task as complete.
    *   `/clear`: Wipe all data.

---

## v2.0.0 - The "Global Nagger" Update 
*Release Date: December 23, 2025*

This major update brings full timezone support, making Nagger Bot truly global! We've also completely overhauled the user experience with smarter commands and friendlier interactions.

### New Features
*   **Timezone Support**: Nagger Bot now lives in *your* time.
    *   Set your timezone via `/timezone`.
    *   Auto-detect using "📍 Send Location" (Mobile).
    *   Manual selection via interactive menu (Desktop).
    *   "Active Hours" and deadlines now respect your local clock.
*   **Smart Quick Add (`/q`)**:
    *   Now supports commas! Example: `/q Buy milk, 5pm, 30m`.
    *   Smarter date parsing: "tomorrow at 5pm", "in 2 hours", "next friday".
*   **Interactive Help**:
    *   Refactored `/help` command to be cleaner and more useful.
    *   Categorized into "Essentials", "Power User", and "All Commands".

### Improvements
*   **Better `/add` Flow**:
    *   Clearer prompts and instructions.
    *   Added `/cancel` command to abort the process at any step.
    *   Warns you if your timezone isn't set.
*   **Connection Stability**: Increased connection timeouts to handle slower networks better.
*   **Database**: Added `users` table to persist user settings.

### Bug Fixes
*   **Daily Reminders**: Fixed a bug where "daily" reminders would spam every minute during the escalation window.
*   **Startup Errors**: Fixed `AttributeError` related to database initialization.
*   **Formatting**: Fixed missing spaces in reminder messages (e.g., `/done 1` instead of `/done1`).

### Technical
*   Downgraded `timezonefinder` to v5.2.0 for better Windows compatibility.
*   Refactored `models.py` and `utils.py` for timezone-aware datetime handling.



## v2.1.0 - The "Lightning Nagger" Update 
*Release Date: December 26, 2025*

A performance-focused release that makes Nagger Bot faster and more reliable than ever. Under-the-hood improvements ensure buttery-smooth responses.

### Performance Improvements
*   **Faster Response Times**: All commands now respond noticeably quicker.
    *   Database connection pooling for efficient resource usage.
    *   Optimized query execution across all operations.
*   **Non-Blocking Logging**: Activity tracking and error logging run in the background, never slowing down your interactions.

### Bug Fixes
*   **Timezone Handling**: Fixed `invalid input for query argument` errors when updating reminders.
    *   `last_sent` and `next_reminder` datetimes are now properly converted to naive UTC before database operations.
*   **Reminder Frequency**: Fixed an issue where reminders weren't following the configured frequency correctly.

### Monitoring & Reliability
*   **Command Metrics**: All commands now report processing times to the database.
    *   Enables performance monitoring via the admin dashboard.
*   **Smart Error Logging**: Critical server-side errors are now logged to the database with full stack traces.
    *   User-caused errors (invalid inputs, blocked bots) are filtered out to reduce noise.
*   **Improved Error Handler**: Global error handler now distinguishes between user errors and system failures.

### Technical
*   Added `@track_activity` decorator to all command handlers.
*   Fire-and-forget async pattern (`asyncio.create_task()`) for zero-impact logging.
*   Extended ignored error list for better error classification.

---