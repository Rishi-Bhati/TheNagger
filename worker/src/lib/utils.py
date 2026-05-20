"""
lib/utils.py — Pure-Python utility functions, zero external dependencies.
Uses our custom, lightweight cf_tz module instead of standard zoneinfo/pytz.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict
import logging

from lib.cf_tz import get_timezone

logger = logging.getLogger(__name__)

UTC = timezone.utc


def _get_tz(tz_str: str):
    return get_timezone(tz_str)


def parse_datetime(date_string: str, user_timezone: str = "UTC") -> Optional[datetime]:
    """Parse various datetime formats, return naive UTC datetime."""
    date_string = date_string.strip()
    tz = _get_tz(user_timezone)
    now = datetime.now(tz)

    formats = [
        "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M",
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%H:%M",
    ]
    parsed_dt = None
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            if fmt == "%H:%M":
                dt = now.replace(hour=dt.hour, minute=dt.minute, second=0, microsecond=0)
                if dt <= now:
                    dt += timedelta(days=1)
            elif len(fmt) <= 10:
                dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            parsed_dt = dt
            break
        except ValueError:
            continue

    if not parsed_dt:
        parsed_dt = parse_relative_time(date_string, now)

    if parsed_dt:
        return parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)
    return None


def parse_relative_time(time_string: str, now: datetime) -> Optional[datetime]:
    time_string = time_string.lower().strip()

    match = re.match(r"in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)", time_string)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        if "minute" in unit: return now + timedelta(minutes=amount)
        if "hour" in unit:   return now + timedelta(hours=amount)
        if "day" in unit:    return now + timedelta(days=amount)

    match = re.match(r"tomorrow\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_string)
    if match:
        h, m, p = int(match.group(1)), int(match.group(2) or 0), match.group(3)
        if p == "pm" and h < 12: h += 12
        elif p == "am" and h == 12: h = 0
        return (now + timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)

    match = re.match(r"today\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_string)
    if match:
        h, m, p = int(match.group(1)), int(match.group(2) or 0), match.group(3)
        if p == "pm" and h < 12: h += 12
        elif p == "am" and h == 12: h = 0
        result = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if result <= now: result += timedelta(days=1)
        return result

    match = re.match(
        r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_string)
    if match:
        day_map = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
        h, m, p = int(match.group(2)), int(match.group(3) or 0), match.group(4)
        if p == "pm" and h < 12: h += 12
        elif p == "am" and h == 12: h = 0
        days_ahead = day_map[match.group(1)] - now.weekday()
        if days_ahead <= 0: days_ahead += 7
        return (now + timedelta(days=days_ahead)).replace(hour=h, minute=m, second=0, microsecond=0)

    return None


def parse_frequency(fs: str) -> Optional[Tuple[str, int]]:
    fs = fs.lower().strip()
    shortcuts = {
        "hourly":("hours",1),"every hour":("hours",1),"daily":("daily",1),"every day":("daily",1),
        "15m":("minutes",15),"30m":("minutes",30),"45m":("minutes",45),
        "1h":("hours",1),"2h":("hours",2),"3h":("hours",3),"4h":("hours",4),
        "6h":("hours",6),"8h":("hours",8),"12h":("hours",12),
    }
    if fs in shortcuts:
        return shortcuts[fs]
    match = re.match(r"(?:every\s+)?(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|m|h)", fs)
    if match:
        v, u = int(match.group(1)), match.group(2)
        if u in ("minute","minutes","min","mins","m"): return ("minutes", v)
        if u in ("hour","hours","hr","hrs","h"):       return ("hours", v)
    match = re.match(r"(\d+)\s+times?\s+per\s+(day|hour)", fs)
    if match:
        t, p = int(match.group(1)), match.group(2)
        if p == "day":  return ("hours",  max(1, 24 // t))
        if p == "hour": return ("minutes", max(1, 60 // t))
    return None


def format_task_list(tasks: List[Dict], user_timezone: str = "UTC") -> str:
    if not tasks:
        return "📭 No active tasks found."
    tz = _get_tz(user_timezone)
    message = "📋 *Your Active Tasks:*\n\n"
    for task in tasks:
        uid = task.get("user_task_id")
        deadline_utc = task.get("deadline")
        if isinstance(deadline_utc, str):
            deadline_utc = datetime.fromisoformat(deadline_utc.replace("Z", "+00:00"))
        if deadline_utc and deadline_utc.tzinfo is None:
            deadline_utc = deadline_utc.replace(tzinfo=timezone.utc)
        deadline_local = deadline_utc.astimezone(tz) if deadline_utc else None
        status = "✅ Completed" if task.get("completed") else get_task_status(deadline_utc)
        message += f"*{uid}. {escape_markdown(task.get('title',''))}*\n"
        if task.get("description"):
            message += f"   📝 {escape_markdown(task['description'])}\n"
        dl_str = deadline_local.strftime("%Y-%m-%d %H:%M") if deadline_local else "unknown"
        message += f"   ⏰ Deadline: {dl_str}\n   📊 Status: {status}\n"
        for r in (task.get("reminders") or [])[:1]:
            message += f"   🔔 Reminder: {format_frequency(r['frequency_type'], r['frequency_value'])}\n"
        message += f"   _Actions: /done {uid} | /test {uid} | /delete {uid}_\n\n"
    return message


def get_task_status(deadline: Optional[datetime]) -> str:
    if not deadline: return "❓ Unknown"
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if deadline < now: return "❌ Overdue"
    d = deadline - now
    days, hours, mins = d.days, d.seconds // 3600, (d.seconds % 3600) // 60
    if days > 0:  return f"⏳ {days}d {hours}h left"
    if hours > 0: return f"⏳ {hours}h {mins}m left"
    return f"⏳ {mins}m left"


def format_frequency(freq_type: str, freq_value: int) -> str:
    if freq_type == "minutes": return "Every minute" if freq_value == 1 else f"Every {freq_value} minutes"
    if freq_type == "hours":   return "Every hour"   if freq_value == 1 else f"Every {freq_value} hours"
    if freq_type == "daily":   return "Daily"
    return f"Every {freq_value} {freq_type}"


def escape_markdown(text: str) -> str:
    if not text: return ""
    for c in ["_", "*", "[", "]", "(", ")", "~", "`"]:
        text = text.replace(c, f"\\{c}")
    return text


def time_until_deadline_str(deadline: datetime) -> str:
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - now
    if delta.total_seconds() <= 0: return "overdue"
    days, hours, mins = delta.days, delta.seconds // 3600, (delta.seconds % 3600) // 60
    if days > 0:  return f"{days}d {hours}h"
    if hours > 0: return f"{hours}h {mins}m"
    return f"{mins}m"
