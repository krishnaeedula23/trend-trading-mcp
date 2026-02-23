"""US equity market hours detection for smart anchor selection."""

from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")


def is_market_open(now: datetime | None = None) -> bool:
    """
    Check if US equity markets are currently open.

    Mon-Fri 9:30-16:00 ET. No holiday calendar — holidays are simply
    closed, so auto-detection correctly defaults to use_current_close=True.
    """
    now = now or datetime.now(_ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_ET)
    else:
        now = now.astimezone(_ET)

    # Weekends
    if now.weekday() >= 5:
        return False

    # Market hours: 9:30 - 16:00 ET
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now < market_close


def resolve_use_current_close(explicit: bool | None = None, now: datetime | None = None) -> bool:
    """
    Resolve the use_current_close flag.

    - If explicit is a bool, honor it directly.
    - If None (auto), detect from market hours: closed → True, open → False.
    """
    if explicit is not None:
        return explicit
    return not is_market_open(now)
