"""
lib/commands.py — All Telegram command handlers.
/add = quick-add (one liner). /d = detailed multi-step wizard.
"""
import logging
from datetime import datetime, timezone
from .utils import (
    parse_datetime, parse_frequency, format_task_list,
    escape_markdown, time_until_deadline_str,
)
from .timezone_lookup import get_timezone_from_coords
from .cf_tz import get_timezone, is_valid_timezone

logger = logging.getLogger(__name__)

# ── /start ────────────────────────────────────────────────────────────────────
async def cmd_start(chat_id, tg):
    await tg.send_message(chat_id, (
        "👋 *Welcome to Nagger Bot!*\n\n"
        "I'll keep bothering you until you finish your tasks 😈\n\n"
        "*Commands:*\n"
        "• `/add Title, Deadline, Freq` — Quick add\n"
        "• `/d` — Detailed step-by-step add\n"
        "• `/list` — View active tasks\n"
        "• `/done N` — Mark complete\n"
        "• `/delete N` — Delete task\n"
        "• `/edit N field value` — Edit a task\n"
        "• `/test N` — Send test reminder\n"
        "• `/timezone` — Set your timezone\n"
        "• `/clear` — Delete all tasks\n\n"
        "*Quick add example:*\n"
        "`/add Buy groceries, in 2 hours, 30m`"
    ))

# ── /help ─────────────────────────────────────────────────────────────────────
async def cmd_help(chat_id, tg):
    await tg.send_message(chat_id, (
        "📖 *Nagger Bot Help*\n\n"
        "🚀 *Quick Add (Primary)*\n"
        "`/add <Title>, <Deadline>, <Frequency>`\n"
        "_Example: `/add Finish report, tomorrow 5pm, 1h`_\n\n"
        "🧙 *Detailed Wizard*\n"
        "`/d` — I'll ask questions one by one\n\n"
        "📋 *Managing Tasks*\n"
        "• `/list` — See all active tasks\n"
        "• `/done 3` — Complete task #3\n"
        "• `/delete 3` — Delete task #3\n"
        "• `/edit 3 title New name` — Change title\n"
        "• `/edit 3 freq 30m` — Change reminder frequency\n"
        "• `/edit 3 deadline tomorrow 6pm` — Change deadline\n"
        "• `/test 3` — Fire a test reminder now\n\n"
        "⏰ *Frequency shortcuts:*\n"
        "15m, 30m, 45m, 1h, 2h, 4h, 6h, 12h, daily\n\n"
        "🌍 *Timezone:* `/timezone` to set via GPS or text\n"
        "❌ *Cancel wizard:* `/cancel`"
    ))

# ── /add (quick-add) ──────────────────────────────────────────────────────────
async def cmd_quick_add_help(chat_id, tg):
    await tg.send_message(chat_id, (
        "⚡ *Quick Add Format:*\n"
        "`/add <Title>, <Deadline>, <Frequency>`\n\n"
        "*Examples:*\n"
        "• `/add Buy milk, in 2 hours, 30m`\n"
        "• `/add Finish report, tomorrow 5pm, 1h`\n"
        "• `/add Call mom, today 6pm, daily`\n\n"
        "For a guided wizard use `/d`"
    ))

async def cmd_quick_add(chat_id, user_id, text, tg, db):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 2:
        return await cmd_quick_add_help(chat_id, tg)

    title = parts[0]
    deadline_str = parts[1]
    freq_str = parts[2] if len(parts) > 2 else "30m"

    if not title:
        return await tg.send_message(chat_id, "❌ Title cannot be empty.")

    tz = await db.get_user_timezone(user_id)
    deadline = parse_datetime(deadline_str, tz)
    if not deadline:
        return await tg.send_message(chat_id, "❌ Invalid deadline. Try: `in 2 hours`, `tomorrow 5pm`")

    now_utc = datetime.utcnow()
    if deadline <= now_utc:
        return await tg.send_message(chat_id, "❌ Deadline must be in the future.")

    freq = parse_frequency(freq_str)
    if not freq:
        return await tg.send_message(chat_id, "❌ Invalid frequency. Use: 30m, 1h, daily, etc.")

    freq_type, freq_value = freq
    user_task_id = await db.add_task(user_id, title, "", deadline)
    actual_id = await db.get_actual_task_id(user_id, user_task_id)
    await db.add_reminder(
        actual_id, freq_type, freq_value,
        start_time="08:00", end_time="22:00",
        escalation_enabled=True, escalation_threshold=60,
    )

    try:
        dl_local = deadline.replace(tzinfo=timezone.utc).astimezone(get_timezone(tz)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        dl_local = deadline.strftime("%Y-%m-%d %H:%M")

    await tg.send_message(chat_id, (
        f"✅ *Task Created!*\n\n"
        f"📝 *Title:* {escape_markdown(title)}\n"
        f"⏰ *Deadline:* {dl_local}\n"
        f"🔔 *Reminder:* Every {freq_value} {freq_type}\n"
        f"📈 *Escalation:* Enabled\n\n"
        f"Task ID: `{user_task_id}`\n"
        f"• Mark complete: `/done {user_task_id}`\n"
        f"• View all: `/list`"
    ))

# ── /d (detailed wizard) ───────────────────────────────────────────────────────
async def cmd_detailed_add(chat_id, user_id, tg, db):
    tz = await db.get_user_timezone(user_id)
    if tz == "UTC":
        await tg.send_message(chat_id, "⚠️ Your timezone is UTC. Set it with `/timezone` for accurate times.")
    await db.set_conversation_state(user_id, "add_task", "title", {})
    await tg.send_message(chat_id, "📝 *New Task — Step 1/4*\n\nEnter the *task title*:\n\n_/cancel to abort_")

async def handle_wizard_step(chat_id, user_id, text, state, tg, db):
    """Route a free-text message to the right wizard step handler."""
    cmd = state.get("command")
    step = state.get("step")
    data = state.get("data") or {}

    if cmd == "add_task":
        await _wizard_add_task(chat_id, user_id, text, step, data, tg, db)
    elif cmd == "timezone":
        await _wizard_timezone_text(chat_id, user_id, text, step, tg, db)

async def _wizard_add_task(chat_id, user_id, text, step, data, tg, db):
    if step == "title":
        if len(text) > 100:
            return await tg.send_message(chat_id, "❌ Title too long (max 100 chars). Try again:")
        data["title"] = text
        await db.set_conversation_state(user_id, "add_task", "description", data)
        await tg.send_message(chat_id, "📄 *Step 2/4* — Enter a *description*:\n_(or type `skip`)_")

    elif step == "description":
        data["description"] = "" if text.lower() == "skip" else text
        await db.set_conversation_state(user_id, "add_task", "deadline", data)
        await tg.send_message(chat_id, (
            "⏰ *Step 3/4* — When is the *deadline*?\n\n"
            "*Examples:*\n• `in 2 hours`\n• `tomorrow at 3pm`\n• `2025-12-25 15:30`"
        ))

    elif step == "deadline":
        tz = await db.get_user_timezone(user_id)
        deadline = parse_datetime(text, tz)
        if not deadline or deadline <= datetime.utcnow():
            return await tg.send_message(chat_id, "❌ Invalid or past deadline. Try again:")
        data["deadline"] = deadline.isoformat()
        await db.set_conversation_state(user_id, "add_task", "frequency", data)
        await tg.send_message_with_inline_keyboard(chat_id,
            "🔔 *Step 4/4* — How often should I remind you?",
            [
                [{"text": "Every 15 min", "callback_data": "wfreq_minutes_15"},
                 {"text": "Every 30 min", "callback_data": "wfreq_minutes_30"}],
                [{"text": "Every hour", "callback_data": "wfreq_hours_1"},
                 {"text": "Every 2 hours", "callback_data": "wfreq_hours_2"}],
                [{"text": "Every 4 hours", "callback_data": "wfreq_hours_4"},
                 {"text": "Daily", "callback_data": "wfreq_daily_1"}],
                [{"text": "Custom…", "callback_data": "wfreq_custom"}],
            ]
        )

    elif step == "frequency_custom":
        freq = parse_frequency(text)
        if not freq:
            return await tg.send_message(chat_id, "❌ Invalid frequency. Try: `every 45 minutes`, `3h`")
        data["freq_type"], data["freq_value"] = freq
        await _finish_wizard(chat_id, user_id, data, tg, db)

async def _finish_wizard(chat_id, user_id, data, tg, db):
    deadline = datetime.fromisoformat(data["deadline"])
    tz_str = await db.get_user_timezone(user_id)
    user_task_id = await db.add_task(user_id, data["title"], data.get("description", ""), deadline)
    actual_id = await db.get_actual_task_id(user_id, user_task_id)
    await db.add_reminder(
        actual_id,
        data["freq_type"], data["freq_value"],
        start_time="08:00", end_time="22:00",
        escalation_enabled=True, escalation_threshold=60,
    )
    await db.clear_conversation_state(user_id)
    try:
        dl_local = deadline.replace(tzinfo=timezone.utc).astimezone(get_timezone(tz_str)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        dl_local = deadline.strftime("%Y-%m-%d %H:%M")

    await tg.send_message(chat_id, (
        f"✅ *Task Created!*\n\n"
        f"📝 *Title:* {escape_markdown(data['title'])}\n"
        f"📄 *Desc:* {escape_markdown(data.get('description') or 'None')}\n"
        f"⏰ *Deadline:* {dl_local}\n"
        f"🔔 *Reminder:* Every {data['freq_value']} {data['freq_type']}\n\n"
        f"Task ID: `{user_task_id}`\n"
        f"• `/done {user_task_id}` — Mark complete\n"
        f"• `/test {user_task_id}` — Test reminder"
    ))

# ── /list ─────────────────────────────────────────────────────────────────────
async def cmd_list(chat_id, user_id, tg, db):
    tasks = await db.get_user_tasks(user_id)
    tz = await db.get_user_timezone(user_id)
    if not tasks:
        return await tg.send_message(chat_id, "📭 No active tasks.\n\nUse `/add` to create one!")
    await tg.send_message(chat_id, format_task_list(tasks, tz))

# ── /done ─────────────────────────────────────────────────────────────────────
async def cmd_done(chat_id, user_id, text, tg, db):
    parts = text.strip().split()
    if len(parts) < 2:
        return await tg.send_message(chat_id, "❌ Usage: `/done <ID>`  e.g. `/done 3`")
    try:
        uid = int(parts[1])
    except ValueError:
        return await tg.send_message(chat_id, "❌ Invalid task ID.")

    task = await db.get_task_by_id(user_id, uid)
    if not task:
        return await tg.send_message(chat_id, "❌ Task not found.")
    if task.get("completed"):
        return await tg.send_message(chat_id, "ℹ️ Already completed.")
    await db.update_task(task["id"], completed=True, completed_at=datetime.utcnow())
    await tg.send_message(chat_id, f"✅ *{escape_markdown(task['title'])}* marked as done! 🎉")

# ── /delete ───────────────────────────────────────────────────────────────────
async def cmd_delete(chat_id, user_id, text, tg, db):
    parts = text.strip().split()
    if len(parts) < 2:
        return await tg.send_message(chat_id, "❌ Usage: `/delete <ID>`  e.g. `/delete 3`")
    try:
        uid = int(parts[1])
    except ValueError:
        return await tg.send_message(chat_id, "❌ Invalid task ID.")

    task = await db.get_task_by_id(user_id, uid)
    if not task:
        return await tg.send_message(chat_id, "❌ Task not found.")
    await db.delete_task(task["id"])
    await tg.send_message(chat_id, f"🗑️ Task *{escape_markdown(task['title'])}* deleted.")

# ── /edit ─────────────────────────────────────────────────────────────────────
async def cmd_edit(chat_id, user_id, text, tg, db):
    # Syntax: /edit <id> <field> <value...>
    # Fields: title, freq, deadline
    parts = text.strip().split(None, 3)
    if len(parts) < 4:
        return await tg.send_message(chat_id, (
            "❌ Usage: `/edit <ID> <field> <value>`\n\n"
            "*Examples:*\n"
            "• `/edit 3 title New task name`\n"
            "• `/edit 3 freq 1h`\n"
            "• `/edit 3 deadline tomorrow 5pm`"
        ))
    try:
        uid = int(parts[1])
    except ValueError:
        return await tg.send_message(chat_id, "❌ Invalid task ID.")

    field = parts[2].lower()
    value = parts[3].strip()

    task = await db.get_task_by_id(user_id, uid)
    if not task:
        return await tg.send_message(chat_id, "❌ Task not found.")

    if field == "title":
        await db.update_task(task["id"], title=value)
        await tg.send_message(chat_id, "✅ Title updated!")

    elif field in ("freq", "frequency"):
        freq = parse_frequency(value)
        if not freq:
            return await tg.send_message(chat_id, "❌ Invalid frequency. Use: 30m, 1h, daily, etc.")
        reminders = task.get("reminders") or []
        if not reminders:
            return await tg.send_message(chat_id, "❌ No reminder found for this task.")
        await db.update_reminder(reminders[0]["id"], frequency_type=freq[0], frequency_value=freq[1])
        await tg.send_message(chat_id, "✅ Frequency updated!")

    elif field == "deadline":
        tz = await db.get_user_timezone(user_id)
        deadline = parse_datetime(value, tz)
        if not deadline or deadline <= datetime.utcnow():
            return await tg.send_message(chat_id, "❌ Invalid or past deadline.")
        await db.update_task(task["id"], deadline=deadline)
        await tg.send_message(chat_id, "✅ Deadline updated!")

    else:
        await tg.send_message(chat_id, "❌ Unknown field. Use: `title`, `freq`, or `deadline`")

# ── /test ─────────────────────────────────────────────────────────────────────
async def cmd_test(chat_id, user_id, text, tg, db):
    parts = text.strip().split()
    if len(parts) < 2:
        return await tg.send_message(chat_id, "❌ Usage: `/test <ID>`")
    try:
        uid = int(parts[1])
    except ValueError:
        return await tg.send_message(chat_id, "❌ Invalid task ID.")

    task = await db.get_task_by_id(user_id, uid)
    if not task:
        return await tg.send_message(chat_id, "❌ Task not found.")

    deadline = task.get("deadline")
    if isinstance(deadline, str):
        from datetime import datetime as _dt
        deadline = _dt.fromisoformat(deadline.replace("Z", "+00:00"))
    dl_str = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "unknown"
    tl = time_until_deadline_str(deadline) if deadline else "?"

    await tg.send_message(chat_id, (
        f"🧪 *Test Reminder*\n\n"
        f"🔔 *Reminder*: {escape_markdown(task['title'])}\n\n"
        f"⏰ Deadline: {dl_str} ({tl} left)\n\n"
        f"_Reply /done {uid} to mark as complete_"
    ))

# ── /clear ────────────────────────────────────────────────────────────────────
async def cmd_clear(chat_id, user_id, tg, db):
    await tg.send_message_with_inline_keyboard(chat_id,
        "⚠️ *Warning!*\n\nThis will delete ALL your tasks permanently.\nAre you sure?",
        [
            [{"text": "✅ Yes, clear all", "callback_data": f"clear_confirm_{user_id}"},
             {"text": "❌ Cancel", "callback_data": "clear_cancel"}]
        ]
    )

# ── /timezone ─────────────────────────────────────────────────────────────────
async def cmd_timezone(chat_id, user_id, text, tg, db):
    parts = text.strip().split(None, 1)
    # Direct: /timezone Asia/Kolkata
    if len(parts) == 2:
        tz_str = parts[1].strip()
        if is_valid_timezone(tz_str):
            await db.set_user_timezone(user_id, tz_str)
            return await tg.send_message(chat_id, f"✅ Timezone set to `{tz_str}`")
        else:
            return await tg.send_message(chat_id, f"❌ Unknown timezone: `{tz_str}`\n\nTry e.g. `Asia/Kolkata`, `Europe/London`")

    # Interactive: ask for location
    current = await db.get_user_timezone(user_id)
    await db.set_conversation_state(user_id, "timezone", "awaiting_location", {})
    await tg.send_message_with_reply_keyboard(
        chat_id,
        f"🌍 *Timezone Settings*\n\nCurrent: `{current}`\n\nShare your location for automatic detection, or tap *Enter Manually* to type it.",
        [[{"text": "📍 Send Location", "request_location": True}],
         [{"text": "✏️ Enter Manually"}]],
    )

async def handle_location_message(message, tg, db):
    """Handle GPS location sent by user for timezone detection."""
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    loc = message.get("location", {})
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    if lat is None or lng is None:
        return await tg.send_message(chat_id, "❌ Could not read location.")

    tz_str = await get_timezone_from_coords(lat, lng)
    await db.set_user_timezone(user_id, tz_str)
    await db.clear_conversation_state(user_id)
    await tg.remove_reply_keyboard(chat_id, f"✅ Timezone set to `{tz_str}`")

async def _wizard_timezone_text(chat_id, user_id, text, step, tg, db):
    if step == "awaiting_location" and text == "✏️ Enter Manually":
        await db.set_conversation_state(user_id, "timezone", "awaiting_text", {})
        return await tg.send_message(chat_id, "Type your timezone (e.g. `Asia/Kolkata`, `Europe/Berlin`):")
    if step == "awaiting_text":
        tz_input = text.strip()
        if is_valid_timezone(tz_input):
            await db.set_user_timezone(user_id, tz_input)
            await db.clear_conversation_state(user_id)
            await tg.remove_reply_keyboard(chat_id, f"✅ Timezone set to `{tz_input}`")
        else:
            await tg.send_message(chat_id, f"❌ Unknown timezone: `{tz_input}`\n\nTry e.g. `Asia/Kolkata`")

# ── Callback query router ─────────────────────────────────────────────────────
async def handle_callback(callback, tg, db):
    cid = callback["id"]
    data = callback.get("data", "")
    msg = callback.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    user_id = callback.get("from", {}).get("id")

    await tg.answer_callback_query(cid)

    # Clear confirm / cancel
    if data.startswith("clear_confirm_"):
        count = await db.clear_all_user_data(user_id)
        await tg.edit_message_text(chat_id, msg_id,
            f"🗑️ Deleted {count} task(s). Use `/add` to start fresh!")
    elif data == "clear_cancel":
        await tg.edit_message_text(chat_id, msg_id, "❌ Cancelled. Your tasks are safe.")

    # Wizard frequency selection
    elif data.startswith("wfreq_"):
        parts = data.split("_")  # wfreq_minutes_30
        if parts[1] == "custom":
            state = await db.get_conversation_state(user_id) or {}
            d = state.get("data") or {}
            await db.set_conversation_state(user_id, "add_task", "frequency_custom", d)
            await tg.edit_message_text(chat_id, msg_id,
                "Enter custom frequency:\n`every 45 minutes`, `3h`, etc.")
        else:
            freq_type = parts[1]  # minutes/hours/daily
            freq_value = int(parts[2])
            state = await db.get_conversation_state(user_id) or {}
            d = state.get("data") or {}
            d["freq_type"] = freq_type
            d["freq_value"] = freq_value
            await tg.edit_message_text(chat_id, msg_id, "⏳ Creating your task…")
            await _finish_wizard(chat_id, user_id, d, tg, db)

# ── Top-level dispatcher ──────────────────────────────────────────────────────
async def handle_update(update: dict, tg, db):
    """Entry point called from entry.py fetch handler."""
    callback = update.get("callback_query")
    message = update.get("message")

    if callback:
        return await handle_callback(callback, tg, db)

    if not message:
        return

    # Location update (for timezone)
    if "location" in message:
        return await handle_location_message(message, tg, db)

    if "text" not in message:
        return

    text = message["text"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    username = message["from"].get("username")
    full_name = (
        f"{message['from'].get('first_name', '')} {message['from'].get('last_name', '')}".strip()
    )

    # Track activity (best-effort, don't let it break the flow)
    try:
        await db.update_user_activity(user_id, username, full_name)
    except Exception:
        pass

    # Active wizard state takes priority over commands when user types free text
    if not text.startswith("/"):
        state = await db.get_conversation_state(user_id)
        if state:
            return await handle_wizard_step(chat_id, user_id, text, state, tg, db)

    # Command routing
    t = text.split()[0].lower().split("@")[0]  # strip @botname suffix

    if t == "/start":
        await cmd_start(chat_id, tg)
    elif t == "/help":
        await cmd_help(chat_id, tg)
    elif t == "/add":
        rest = text[4:].strip()
        if rest:
            await cmd_quick_add(chat_id, user_id, rest, tg, db)
        else:
            await cmd_quick_add_help(chat_id, tg)
    elif t == "/d":
        await cmd_detailed_add(chat_id, user_id, tg, db)
    elif t == "/list":
        await cmd_list(chat_id, user_id, tg, db)
    elif t == "/done":
        await cmd_done(chat_id, user_id, text, tg, db)
    elif t == "/delete":
        await cmd_delete(chat_id, user_id, text, tg, db)
    elif t == "/edit":
        await cmd_edit(chat_id, user_id, text, tg, db)
    elif t == "/test":
        await cmd_test(chat_id, user_id, text, tg, db)
    elif t == "/clear":
        await cmd_clear(chat_id, user_id, tg, db)
    elif t == "/timezone":
        await cmd_timezone(chat_id, user_id, text, tg, db)
    elif t == "/cancel":
        await db.clear_conversation_state(user_id)
        await tg.remove_reply_keyboard(chat_id, "❌ Operation cancelled.")
