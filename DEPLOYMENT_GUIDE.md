# Deployment Guide for Nagger Bot on Render

## Prerequisites
- Render account (https://render.com)
- PostgreSQL database (can be created on Render)
- Telegram Bot Token (already provided)

## Step 1: Create PostgreSQL Database on Render
1. Go to Render Dashboard
2. Click "New +" → "PostgreSQL"
3. Choose a name (e.g., "nagger-bot-db")
4. Select the free tier
5. Click "Create Database"
6. Wait for database to be created
7. Copy the "External Database URL" - you'll need this

## Step 2: Deploy the Bot
1. Go to Render Dashboard
2. Click "New +" → "Web Service"
3. Connect your GitHub/GitLab repository or use "Public Git repository"
4. Configure the service:
   - **Name**: nagger-bot
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python reminder_bot.py`
   - **Instance Type**: Free

## Step 3: Set Environment Variables
Add these environment variables in Render:
- `TELEGRAM_BOT_TOKEN`: Your bot token (already in .env)
- `DATABASE_URL`: The PostgreSQL URL from Step 1
- `PORT`: Leave empty (Render will auto-assign)
- `PYTHON_VERSION`: 3.11.9

## Step 4: Deploy
1. Click "Create Web Service"
2. Wait for the build and deployment to complete
3. Check the logs for any errors

## Troubleshooting

### Port Binding Issues
The bot now includes a web server that serves a simple HTML page. This satisfies Render's requirement for an open port.

### Database Connection Issues
- Ensure the DATABASE_URL is correctly set
- The bot will automatically create tables on first run

### Python Version Issues
The project includes:
- `runtime.txt` with Python 3.11.9
- `.python-version` file
- `render.yaml` configuration

### Datetime Parsing Errors
If you see "fromisoformat: argument must be str" errors:
- This has been fixed in the code
- The bot now handles both string and datetime objects from PostgreSQL

## Monitoring
- Check Render logs for any errors
- Visit your web service URL to see the status page
- Use `/test<task_id>` command to test reminders

## Local Testing
To test locally before deployment:
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token"
export DATABASE_URL="postgresql://user:pass@localhost/dbname"

# Run the bot
python reminder_bot.py
```

## Important Notes
1. The bot uses polling, not webhooks
2. Free tier on Render may sleep after inactivity
3. Reminders are checked every minute
4. Default quiet hours are 10 PM - 8 AM
