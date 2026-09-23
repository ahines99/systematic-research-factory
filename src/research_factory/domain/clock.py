"""Injectable clocks so tests and replays are deterministic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Returns a fixed instant, advancing by ``step`` on every call."""

    def __init__(self, start: datetime, step: timedelta = timedelta(seconds=1)):
        if start.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware start")
        self._current = start.astimezone(UTC)
        self._step = step

    def now(self) -> datetime:
        value = self._current
        self._current = self._current + self._step
        return value
