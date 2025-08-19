# Nagger Bot - Smart Telegram Reminder System

A persistent Telegram reminder bot that keeps nagging you until you complete your tasks. Perfect for people who tend to ignore single reminders!

## Features

- 📝 **Multiple Tasks**: Manage multiple tasks simultaneously
- 🔔 **Persistent Reminders**: Keeps reminding until task is marked complete
- ⏰ **Flexible Scheduling**: Set reminders every X minutes/hours or daily
- 📈 **Smart Escalation**: Reminders become more frequent near deadlines
- 🌙 **Quiet Hours**: Set active hours to avoid night-time reminders
- 💾 **Persistent Storage**: Tasks survive bot restarts (PostgreSQL database)
- 💬 **Custom Messages**: Set different reminder messages for variety
- 🎯 **Easy Commands**: Simple command interface for all operations

## Commands

- `/start` - Start the bot and see welcome message
- `/add` - Add a new task with customizable reminders
- `/list` - View all your active tasks
- `/edit <task_id>` - Edit a task (coming soon)
- `/delete <task_id>` - Delete a task
- `/done<task_id>` - Mark task as completed (e.g., `/done5`)
- `/test<task_id>` - Send a test reminder
- `/help` - Show detailed help

## Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))
- PostgreSQL database (local or cloud-hosted)

## Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Nagger
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL Database**
   
   **Option A: Local PostgreSQL**
   ```bash
   # Install PostgreSQL if not already installed
   # Create a database
   createdb nagger_bot
   ```
   
   **Option B: Cloud PostgreSQL**
   - Use services like Heroku Postgres, Railway, Supabase, or Neon
   - They provide a DATABASE_URL automatically

4. **Set up environment variables**
   - Copy `.env.example` to `.env`
   - Add your Telegram bot token
   - Add your PostgreSQL DATABASE_URL:
     ```
     TELEGRAM_BOT_TOKEN=your_bot_token_here
     DATABASE_URL=postgresql://user:password@localhost:5432/nagger_bot
     ```

5. **Run the bot**
   ```bash
   python reminder_bot.py
   ```

## Usage Examples

### Adding a Task
1. Send `/add` to the bot
2. Enter task title: "Finish project report"
3. Enter description: "Complete the Q4 analysis section"
4. Set deadline: "tomorrow at 5pm" or "2024-12-25 17:00"
5. Choose reminder frequency: Every 30 minutes
6. Set active hours: 9 AM to 10 PM
7. Enable escalation: Yes

### Quick Task Completion
- When you receive a reminder, it shows the task ID
- Simply send `/done5` (where 5 is your task ID) to mark it complete

### Deadline Formats
- Specific: `2024-12-25 15:30`
- Relative: `in 2 hours`, `in 30 minutes`
- Natural: `tomorrow at 3pm`, `today at 6pm`

## Deployment

### Local Deployment
The bot can run on any machine with Python 3.8+:
```bash
python reminder_bot.py
```

### Cloud Deployment (Recommended)

#### Option 1: Heroku
1. Create a `Procfile`:
   ```
   worker: python reminder_bot.py
   ```
2. Deploy to Heroku and set environment variables

#### Option 2: VPS (Ubuntu/Debian)
1. Install Python and dependencies
2. Use systemd to run as a service:
   ```bash
   sudo nano /etc/systemd/system/nagger-bot.service
   ```
   
   Add:
   ```ini
   [Unit]
   Description=Nagger Telegram Bot
   After=network.target

   [Service]
   Type=simple
   User=your-user
   WorkingDirectory=/path/to/Nagger
   ExecStart=/usr/bin/python3 /path/to/Nagger/reminder_bot.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. Start the service:
   ```bash
   sudo systemctl start nagger-bot
   sudo systemctl enable nagger-bot
   ```

#### Option 3: Docker
Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "reminder_bot.py"]
```

Build and run:
```bash
docker build -t nagger-bot .
docker run -d --name nagger-bot --restart always nagger-bot
```

## Database

The bot uses PostgreSQL for persistent storage. The database tables are created automatically on first run.

### Database Schema
- **tasks**: Stores task information (id, user_id, title, description, deadline, completed status)
- **reminders**: Stores reminder configurations (frequency, active hours, escalation settings)
- **reminder_history**: Tracks sent reminders for each task

### PostgreSQL Setup Options

1. **Local PostgreSQL**:
   ```bash
   # Ubuntu/Debian
   sudo apt install postgresql
   sudo -u postgres createuser --interactive
   sudo -u postgres createdb nagger_bot
   ```

2. **Cloud PostgreSQL Services** (Recommended for hosting):
   - **Railway**: Auto-provisions PostgreSQL with DATABASE_URL
   - **Heroku**: Add Heroku Postgres addon
   - **Supabase**: Free tier available with connection pooling
   - **Neon**: Serverless PostgreSQL with generous free tier

## Customization

### Modify Reminder Templates
Edit `config.py` to change reminder message templates:
```python
REMINDER_TEMPLATE = "Your custom template here"
ESCALATION_TEMPLATE = "Your urgent template here"
```

### Adjust Time Limits
In `config.py`:
```python
DEFAULT_REMINDER_INTERVAL = 30  # minutes
MAX_ESCALATION_FREQUENCY = 5    # minimum minutes between escalated reminders
```

## Troubleshooting

1. **Bot not responding**: Check if the token in `.env` is correct
2. **Reminders not sending**: Ensure the bot is running continuously
3. **Database connection errors**: 
   - Check if PostgreSQL is running
   - Verify DATABASE_URL format is correct
   - Ensure database exists and user has permissions
4. **psycopg2 installation issues**:
   - On Ubuntu/Debian: `sudo apt-get install libpq-dev python3-dev`
   - On macOS: `brew install postgresql`
   - Or use `psycopg2-binary` in requirements.txt (already included)

## Security Notes

- Keep your bot token secret
- The `.env` file should never be committed to public repositories
- Use environment variables for sensitive data in production

## Future Enhancements

- [ ] Edit existing tasks and reminders
- [ ] Recurring tasks (weekly, monthly)
- [ ] Task categories and tags
- [ ] Statistics and productivity tracking
- [ ] Import/export tasks
- [ ] Multiple reminder messages per task
- [ ] Snooze functionality

## License

This project is open source and available under the MIT License.
