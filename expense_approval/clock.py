"""Business dates from an explicitly injectable, timezone-aware time source."""

from collections.abc import Callable
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current aware UTC instant for production callers."""
    return datetime.now(timezone.utc)


def business_date(now: Callable[[], datetime] = utc_now) -> date:
    """Read the source once and return its Asia/Kolkata calendar date.

    Inject an aware datetime source for deterministic tests. Naive values raise
    ValueError; the host's local timezone is never used to interpret the instant.
    Callers capture this date once per initial submission and retain it for revisions.
    """
    instant = now()
    if instant.utcoffset() is None:
        raise ValueError("The time source must return a timezone-aware datetime.")
    return instant.astimezone(ZoneInfo("Asia/Kolkata")).date()
