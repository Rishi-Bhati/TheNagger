"""
lib/cf_tz.py — Lightweight timezone resolver.
Replaces zoneinfo/pytz, works natively in Pyodide/WebAssembly.
"""
from datetime import timezone, timedelta
import re

COMMON_TZS = {
    "utc": 0.0,
    "gmt": 0.0,
    "ist": 5.5,
    "asia/kolkata": 5.5,
    "asia/calcutta": 5.5,
    "europe/london": 0.0,
    "europe/berlin": 1.0,
    "europe/paris": 1.0,
    "gb": 0.0,
    "us/eastern": -5.0,
    "est": -5.0,
    "edt": -4.0,
    "us/central": -6.0,
    "cst": -6.0,
    "cdt": -5.0,
    "us/mountain": -7.0,
    "mst": -7.0,
    "mdt": -6.0,
    "us/pacific": -8.0,
    "pst": -8.0,
    "pdt": -7.0,
}


def get_timezone(tz_str: str) -> timezone:
    """Resolve timezone string or offset to standard datetime.timezone."""
    if not tz_str:
        return timezone.utc

    tz_str_clean = tz_str.lower().strip()

    # 1. Match common tz names
    if tz_str_clean in COMMON_TZS:
        hours = COMMON_TZS[tz_str_clean]
        sign = -1 if hours < 0 else 1
        h, m = divmod(abs(hours) * 60, 60)
        return timezone(timedelta(hours=sign * int(h), minutes=sign * int(m)))

    # 2. Match numeric offset (e.g. +05:30, -04:00, +5:30, -8)
    match = re.match(r"^([+-])(\d{1,2}):?(\d{2})$", tz_str_clean)
    if match:
        sign = -1 if match.group(1) == "-" else 1
        h, m = int(match.group(2)), int(match.group(3))
        return timezone(timedelta(hours=sign * h, minutes=sign * m))

    match = re.match(r"^([+-])(\d{1,2})$", tz_str_clean)
    if match:
        sign = -1 if match.group(1) == "-" else 1
        h = int(match.group(2))
        return timezone(timedelta(hours=sign * h))

    # 3. Fallback to UTC
    return timezone.utc


def is_valid_timezone(tz_str: str) -> bool:
    """Check if string is a recognized timezone name or offset."""
    if not tz_str:
        return False
    tz_str_clean = tz_str.lower().strip()
    if tz_str_clean in COMMON_TZS:
        return True
    if re.match(r"^([+-])\d{1,2}(:?\d{2})?$", tz_str_clean):
        return True
    return False
