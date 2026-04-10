"""FIT file utility functions."""
from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .constants import FIT_EPOCH


def parse_iso(s: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime."""
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    return datetime.fromisoformat(s)


def fit_timestamp(dt: datetime) -> int:
    """Convert datetime to FIT timestamp (seconds since FIT epoch)."""
    return int((dt - FIT_EPOCH).total_seconds())


def resolve_timezone(name: str | None) -> tzinfo:
    """Resolve a timezone by name, defaulting to the system local timezone."""
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {name}") from exc
    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


def fit_local_timestamp(dt: datetime, local_tz: tzinfo) -> int:
    """Convert datetime to a FIT local_timestamp value using a timezone offset."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz)
    offset = dt.astimezone(local_tz).utcoffset()
    offset_s = int(offset.total_seconds()) if offset is not None else 0
    return fit_timestamp(dt) + offset_s
