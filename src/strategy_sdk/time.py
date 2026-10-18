"""Aware timestamps, explicit strategy zones, and normalized timeframes."""

import re
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import DataError


def aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def resolve_timezone(name: str) -> tzinfo:
    if not isinstance(name, str):
        raise DataError("Timezone must be a name or UTC offset")
    if name == "UTC":
        return timezone.utc
    match = re.fullmatch(r"UTC([+-])(\d{2}):(\d{2})", name)
    if match:
        hours, minutes = int(match[2]), int(match[3])
        if hours > 23 or minutes > 59:
            raise DataError("Invalid UTC offset")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(offset if match[1] == "+" else -offset, name)
    try:
        return ZoneInfo(name)
    except (ValueError, ZoneInfoNotFoundError):
        raise DataError(
            "Unknown timezone or unavailable IANA data. Install strategy-sdk[timezones]"
        ) from None


def normalize_timeframe(value: str) -> str:
    if not isinstance(value, str):
        raise DataError("Timeframe must be a string")
    match = re.fullmatch(r"([MHD])([1-9]\d*)|([1-9]\d*)([mhd])", value)
    if not match:
        raise DataError("Timeframe must use M5, H1, D1, 5m, 1h, or 1d notation")
    unit, count = (match[1], match[2]) if match[1] else (match[4].upper(), match[3])
    return f"{unit}{int(count)}"


def timeframe_minutes(value: str) -> int:
    frame = normalize_timeframe(value)
    return int(frame[1:]) * {"M": 1, "H": 60, "D": 1440}[frame[0]]
