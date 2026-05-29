"""
lib/reminder_engine.py

Cron handler logic — called every minute by the Cloudflare scheduled trigger.
Replaces reminder_scheduler.py (APScheduler).

The should_send() logic is ported directly from models.py Reminder.should_send_reminder().
"""
import logging
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from .cf_tz import get_timezone
from .utils import escape_markdown
logger = logging.getLogger(__name__)

REMINDER_TEMPLATE = (
    "🔔 *Reminder*: {title}\n\n{description}\n\n"
    "⏰ Deadline: {deadline}\n\n"
    "_Reply /done {task_id} to mark as complete_"
)
ESCALATION_TEMPLATE = (
    "🚨 *URGENT REMINDER*: {title}\n\n{description}\n\n"
    "⏰ Deadline: {deadline} ({time_left} left)\n\n"
    "_This task is approaching its deadline!_\n"
    "_Reply /done {task_id} to mark as complete_"
)
OVERDUE_TEMPLATE = (
    "🚨 *OVERDUE REMINDER*: {title}\n\n{description}\n\n"
    "⏰ Deadline was: {deadline} (OVERDUE!)\n\n"
    "_Please complete this task!_\n"
    "_Reply /done {task_id} to mark as complete_"
)


async def check_and_send_reminders(tg, db) -> int:
    """
    Main cron entry point. Fetches every pending reminder and sends
    those that are due according to their frequency + quiet hours + escalation.

    Returns the count of reminders sent.
    """
    sent = 0
    try:
        pending = await db.get_pending_reminders()
        for item in pending:
            try:
                user_tz = await db.get_user_timezone(item["user_id"])
                if _should_send(item, user_tz):
                    message = _build_message(item)
                    await tg.send_message(item["user_id"], message)
                    now_utc = datetime.utcnow()
                    await db.update_reminder(
                        item["reminder_id"],
                        last_sent=now_utc,
                    )
                    await db.log_reminder_sent(
                        item["task_id"],
                        "overdue" if _is_overdue(item) else ("escalated" if _is_escalated(item) else "normal"),
                    )
                    sent += 1
                    logger.info(
                        f"Sent reminder for task {item['task_id']} to user {item['user_id']}"
                    )
            except Exception as e:
                logger.error(
                    f"Error processing reminder for task {item.get('task_id')}: {e}\n{traceback.format_exc()}"
                )
    except Exception as e:
        logger.error(f"Fatal error in check_and_send_reminders: {e}\n{traceback.format_exc()}")
    return sent


# ---------------------------------------------------------------------- logic
def _should_send(item: Dict, user_tz: str) -> bool:
    """
    Port of models.py Reminder.should_send_reminder().
    Returns True if this reminder is due right now.
    """
    now_utc = datetime.now(timezone.utc)

    # Parse deadline
    deadline = _parse_dt(item.get("deadline"))
    if not deadline:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)

    # Check quiet hours (active window)
    start_time = item.get("start_time")
    end_time = item.get("end_time")
    if start_time and end_time:
        tz = get_timezone(user_tz)
        now_local = now_utc.astimezone(tz)
        current_hhmm = now_local.strftime("%H:%M")
        if not _in_active_hours(current_hhmm, start_time, end_time):
            return False

    # Parse last_sent
    last_sent = _parse_dt(item.get("last_sent"))

    if last_sent is None:
        return True  # never sent — send now

    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=timezone.utc)
    elapsed_minutes = (now_utc - last_sent).total_seconds() / 60

    # Escalation
    freq_type = item.get("frequency_type", "minutes")
    freq_value = item.get("frequency_value", 30)
    escalation_enabled = item.get("escalation_enabled", False)
    escalation_threshold = item.get("escalation_threshold", 60)

    # We add a small 6-second tolerance (0.1 minutes) to protect against tiny cron execution offsets (e.g. 59.9s)
    tolerance = 0.1

    # Convert base frequency to minutes
    base_minutes = freq_value
    if freq_type == "hours":
        base_minutes *= 60
    elif freq_type == "daily":
        base_minutes *= 24 * 60

    if _is_overdue(item):
        # Keep nagging for overdue tasks at escalated frequency (or normal frequency if not escalated)
        min_interval = max(1, base_minutes // 2) if escalation_enabled else base_minutes
        if base_minutes < 5:
            min_interval = base_minutes
        return elapsed_minutes >= (min_interval - tolerance)

    if escalation_enabled and _is_escalated(item):
        min_interval = max(1, base_minutes // 2)
        if base_minutes < 5:
            min_interval = base_minutes
        return elapsed_minutes >= (min_interval - tolerance)

    # Normal frequency
    return elapsed_minutes >= (base_minutes - tolerance)


def _is_overdue(item: Dict) -> bool:
    """Return True if the task deadline is in the past."""
    deadline = _parse_dt(item.get("deadline"))
    if not deadline:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= deadline


def _is_escalated(item: Dict) -> bool:
    """Return True if the task is within the escalation window."""
    if not item.get("escalation_enabled"):
        return False
    deadline = _parse_dt(item.get("deadline"))
    if not deadline:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    minutes_left = (deadline - datetime.now(timezone.utc)).total_seconds() / 60
    return minutes_left <= item.get("escalation_threshold", 60)


def _in_active_hours(current_hhmm: str, start: str, end: str) -> bool:
    """Check if current_hhmm falls within [start, end] (supports overnight spans)."""
    def to_minutes(t: str) -> int:
        # t may be "HH:MM:SS" from Postgres
        parts = t.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    cur = to_minutes(current_hhmm)
    s = to_minutes(start)
    e = to_minutes(end)
    if s <= e:
        return s <= cur <= e
    # overnight: e.g. 22:00 → 08:00
    return cur >= s or cur <= e


def _build_message(item: Dict) -> str:
    """Build the reminder message string."""
    deadline = _parse_dt(item.get("deadline"))
    deadline_str = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "unknown"

    title = escape_markdown(item["title"])
    desc = escape_markdown(item.get("description") or "")

    if _is_overdue(item):
        return OVERDUE_TEMPLATE.format(
            title=title,
            description=desc,
            deadline=deadline_str,
            task_id=item["user_task_id"],
        )

    if _is_escalated(item):
        # Calculate time left
        if deadline and deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        minutes_left = int(
            (deadline - datetime.now(timezone.utc)).total_seconds() / 60
        ) if deadline else 0
        h, m = divmod(minutes_left, 60)
        time_left = f"{h}h {m}m" if h else f"{m}m"
        return ESCALATION_TEMPLATE.format(
            title=title,
            description=desc,
            deadline=deadline_str,
            time_left=time_left,
            task_id=item["user_task_id"],
        )

    custom = item.get("custom_messages")
    if custom and isinstance(custom, list) and len(custom) > 0:
        last_sent = item.get("last_sent") or ""
        idx = hash(str(last_sent)) % len(custom)
        return (
            f"🔔 *Reminder*: {title}\n\n"
            f"{escape_markdown(custom[idx])}\n\n"
            f"⏰ Deadline: {deadline_str}\n\n"
            f"_Reply /done {item['user_task_id']} to mark as complete_"
        )

    return REMINDER_TEMPLATE.format(
        title=title,
        description=desc,
        deadline=deadline_str,
        task_id=item["user_task_id"],
    )


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
