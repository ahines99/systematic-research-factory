"""Trading calendar: weekdays, 16:00 America/New_York close.

Exchange holidays are not modelled (documented simplification): every weekday is a session.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import numpy.typing as npt

EASTERN = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)
SESSION_MINUTES = 390  # 09:30-16:00


def trading_days(start: date, end: date) -> npt.NDArray[np.datetime64]:
    """All weekdays in [start, end]."""
    days = np.arange(
        np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"), dtype="datetime64[D]"
    )
    return days[np.is_busday(days)]


def close_utc(day: date) -> datetime:
    return datetime.combine(day, MARKET_CLOSE, tzinfo=EASTERN).astimezone(UTC)


def close_epochs(days: npt.NDArray[np.datetime64]) -> npt.NDArray[np.int64]:
    """UTC epoch seconds of each session's close."""
    return np.array([int(close_utc(d.item()).timestamp()) for d in days], dtype=np.int64)


def first_close_at_or_after(epochs: npt.NDArray[np.int64], ts: datetime) -> int:
    """Index of the first session whose close is at or after ``ts`` (len(epochs) if none)."""
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return int(np.searchsorted(epochs, int(ts.timestamp()), side="left"))


def last_close_at_or_before(epochs: npt.NDArray[np.int64], ts: datetime) -> int:
    """Index of the last session whose close is at or before ``ts`` (-1 if none)."""
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return int(np.searchsorted(epochs, int(ts.timestamp()), side="right")) - 1


def execution_lag_sessions(execution_delay_minutes: int) -> int:
    """Sessions between the decision close and the execution close.

    A zero delay means trading at the same close the signal was computed on, which is
    not achievable in practice; the leakage audit flags it. Any positive delay up to one
    session executes at the next close, and each further 390 minutes adds a session.
    """
    if execution_delay_minutes < 0:
        raise ValueError("delay must be non-negative")
    return -(-execution_delay_minutes // SESSION_MINUTES)
