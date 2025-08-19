# Nagger Bot - Quick Start Guide

## ✅ Setup Complete!

Your bot is now ready to use. Here's how to get started:

## 1. Start the Bot

Run this command in your terminal:
```bash
python reminder_bot.py
```

The bot will start and display:
```
2024-XX-XX XX:XX:XX - __main__ - INFO - Bot initialized successfully
2024-XX-XX XX:XX:XX - __main__ - INFO - Starting bot...
```

## 2. Open Telegram

1. Open Telegram on your phone or desktop
2. Search for your bot (you can find it by the username you set when creating it with BotFather)
3. Start a conversation by clicking "Start" or sending `/start`

## 3. Basic Usage

### Create Your First Task
1. Send `/add` to the bot
2. Follow the prompts:
   - Enter a task title (e.g., "Take medication")
   - Enter a description or type "skip"
   - Set a deadline (e.g., "in 4 hours" or "tomorrow at 9pm")
   - Choose reminder frequency from the buttons
   - Select active hours (24/7 or custom)
   - Enable/disable escalation

### View Your Tasks
- Send `/list` to see all active tasks

### Complete a Task
- When you get a reminder, note the task ID
- Send `/done<ID>` (e.g., `/done1`) to mark it complete

## 4. Example Workflow

```
You: /add
Bot: Please enter the task title:
You: Finish project report
Bot: Great! Now enter a description:
You: Complete the financial analysis section
Bot: When is the deadline?
You: tomorrow at 5pm
Bot: [Shows frequency options buttons]
You: [Click "Every 30 mins"]
Bot: [Shows hours options]
You: [Click "Custom Hours"]
Bot: Please enter start time:
You: 09:00
Bot: Please enter end time:
You: 22:00
Bot: Enable escalation?
You: [Click "Yes"]
Bot: ✅ Task Created Successfully!
```

## 5. Keep the Bot Running

### For Testing/Development
Just keep the terminal window open where you ran `python reminder_bot.py`

### For Production (24/7 Operation)

**Option 1: Screen/Tmux (Linux/Mac)**
```bash
screen -S nagger-bot
python reminder_bot.py
# Press Ctrl+A then D to detach
# To reattach: screen -r nagger-bot
```

**Option 2: Windows Task Scheduler**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger to "When computer starts"
4. Set action to start program: `python.exe`
5. Add arguments: `C:\Users\radhe\Stuff\Nagger\reminder_bot.py`

**Option 3: PM2 (Cross-platform)**
```bash
npm install -g pm2
pm2 start reminder_bot.py --interpreter python
pm2 save
pm2 startup
```

## 6. Troubleshooting

### Bot not responding?
- Check if the script is still running
- Verify your internet connection
- Check the terminal for error messages

### Reminders not sending?
- Make sure the bot is running continuously
- Check if the task deadline hasn't passed
- Verify active hours settings

### Need to stop the bot?
- Press `Ctrl+C` in the terminal

## 7. Tips

- Set realistic reminder frequencies (every 5 minutes might be too much!)
- Use escalation for important tasks
- Set quiet hours to avoid night reminders
- Test reminders with `/test<task_id>` before relying on them

## Ready to Go!

Your bot is configured and ready. Start it up and never forget a task again! 🎉
