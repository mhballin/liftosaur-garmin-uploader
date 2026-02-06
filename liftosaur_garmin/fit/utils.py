"""FIT file utility functions."""
from datetime import datetime, timezone
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