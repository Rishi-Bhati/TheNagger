# Nagger Bot - Your Personal Productivity Bully

## Why I Built This

My brain has the memory of a goldfish (yeah)... I forget stuff within minutes, so I built something that literally annoys me until I do the damn task. It’s less of a to-do list and more like a personal bully that keeps nagging me (literally), basically my own toxic productivity buddy.

If you're like me and need constant, relentless reminders to get things done, this bot is for you.

## What It Does

Nagger Bot is a Telegram bot designed to be your personal task manager. It allows you to quickly add tasks, set deadlines, and configure reminders that will keep pinging you until you mark the task as complete.

### Key Features:
- **Quick Add**: Add tasks in a single line with natural language.
- **Timezone Support**: Reminders are sent based on your local time (no more 3 AM wake-up calls!).
- **Customizable Reminders**: Set reminders at any frequency (minutes, hours, or daily).
- **Active Hours**: Configure reminders to only be active during specific hours (e.g., 8 AM - 10 PM).
- **Escalation Mode**: Reminders get more frequent as the deadline approaches.
- **User-Specific IDs**: Your task IDs always start from 1, even in a multi-user environment.
- **Clear Command**: Wipe all your tasks and start fresh.

## Commands

| Command | Description | Example |
| --- | --- | --- |
| `/start` | Start the bot and see the welcome message. | `/start` |
| `/q` | Quickly add a new task. | `/q Buy milk, in 2 hours, 30m` |
| `/add` | Add a new task with full customization. | `/add` |
| `/list` | View all your active tasks. | `/list` |
| `/done <ID>` | Mark a task as completed. | `/done 1` |
| `/delete <ID>`| Delete a task. | `/delete 1` |
| `/test <ID>` | Send a test reminder for a task. | `/test 1` |
| `/timezone` | Set your local timezone. | `/timezone` |
| `/clear` | Delete all your tasks and start fresh. | `/clear` |
| `/help` | Show the detailed help message. | `/help` |

## Quick Add Format

The `/q` command is the fastest way to add a task. The format is:
`/q <title>, <deadline>, <frequency>`

(Note: You can use commas `,` or pipes `|` as separators)

### Deadline Formats:
- **Relative**: `in 2 hours`, `in 30 minutes`
- **Natural**: `tomorrow at 3pm`, `today at 6pm`
- **Specific**: `2024-12-25 15:30`

### Frequency Shortcuts:
- `15m`, `30m`, `45m`
- `1h`, `2h`, `4h`, `8h`, `12h`
- `daily`, `hourly`

## Timezone Support (NEW!)

Nagger Bot now supports user-specific timezones!
1. Run `/timezone`.
2. **Mobile**: Tap "📍 Send Location" for auto-detection.
3. **Desktop**: Select "Manual Selection" to choose your region and city.

Once set, all deadlines and "Active Hours" will respect your local time.

## Tech Stack

- **Language**: Python 3
- **Framework**: `python-telegram-bot`
- **Database**: PostgreSQL
- **Scheduler**: `apscheduler`

