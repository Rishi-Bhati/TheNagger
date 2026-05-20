"""
lib/timezone_lookup.py — Lat/lng to IANA timezone via CF built-in fetch.
"""
import logging
from .cf_fetch import cf_get

logger = logging.getLogger(__name__)

TIMEZONE_API = "https://timeapi.io/api/timezone/coordinate"


async def get_timezone_from_coords(lat: float, lng: float) -> str:
    try:
        data = await cf_get(TIMEZONE_API, params={"latitude": lat, "longitude": lng})
        tz = data.get("timeZone") or data.get("timezone")
        if tz:
            return tz
    except Exception as e:
        logger.error(f"Timezone lookup failed ({lat},{lng}): {e}")
    return "UTC"
