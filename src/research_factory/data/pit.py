"""Point-in-time data access (RSF-016).

Every read requires a timezone-aware ``as_of`` and never returns anything whose
knowledge time is later than ``as_of``:

* filings are known at SEC acceptance time;
* a session's price is known at that session's 16:00 ET close;
* listing status is known on the day; a future delisting date is hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from functools import cached_property
from typing import Any

import numpy as np

from ..domain.errors import AsOfRequiredError, InvalidInputError, NotFoundError
from .calendar import last_close_at_or_before
from .fundamentals import FilingIndex
from .world import Filing, MarketDataset, Security, TickerInterval


def require_as_of(as_of: datetime | None) -> datetime:
    if as_of is None:
        raise AsOfRequiredError("every market or filing query requires as_of")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise AsOfRequiredError("as_of must be timezone-aware (e.g. 2023-12-29T21:00:00Z)")
    return as_of


@dataclass(frozen=True)
class PriceRow:
    security_id: str
    session: date
    raw_close: float
    split_ratio: float
    adjusted_return: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "security_id": self.security_id,
            "session": self.session.isoformat(),
            "raw_close": self.raw_close,
            "split_ratio": self.split_ratio,
            "adjusted_return": self.adjusted_return,
        }


def _hide_future_listing(sec: Security, day: date) -> Security:
    """What was knowable about a security on ``day``: future delistings and tickers are hidden."""
    listed_to = sec.listed_to if sec.listed_to is not None and sec.listed_to <= day else None
    tickers = tuple(
        TickerInterval(t.ticker, t.start, t.end if t.end is not None and t.end <= day else None)
        for t in sec.tickers
        if t.start <= day
    )
    return replace(
        sec,
        listed_to=listed_to,
        tickers=tickers,
        delisting_return=sec.delisting_return if listed_to is not None else None,
    )


class PointInTimeData:
    def __init__(self, dataset: MarketDataset):
        self.dataset = dataset

    @cached_property
    def filing_index(self) -> FilingIndex:
        return FilingIndex(self.dataset.filings)

    def last_session_index(self, as_of: datetime) -> int:
        return last_close_at_or_before(self.dataset.closes, require_as_of(as_of))

    def filings_as_of(
        self, as_of: datetime | None, security_ids: set[str] | None = None, form: str | None = None
    ) -> list[Filing]:
        ts = require_as_of(as_of)
        return [
            f
            for f in self.dataset.filings
            if f.accepted_at <= ts
            and (security_ids is None or f.security_id in security_ids)
            and (form is None or f.form == form)
        ]

    def universe_as_of(self, as_of: datetime | None) -> list[Security]:
        t = self.last_session_index(require_as_of(as_of))
        if t < 0:
            return []
        day = self.dataset.day(t)
        return [_hide_future_listing(s, day) for s in self.dataset.securities if s.is_listed(day)]

    def security(self, security_id: str) -> Security:
        for s in self.dataset.securities:
            if s.security_id == security_id:
                return s
        raise NotFoundError(f"unknown security {security_id}")

    def resolve_ticker(self, ticker: str, as_of: datetime | None) -> Security | None:
        """Ticker → security as of a date. Tickers get reused, so the date matters."""
        t = self.last_session_index(require_as_of(as_of))
        if t < 0:
            return None
        day = self.dataset.day(t)
        for s in self.dataset.securities:
            if s.ticker_on(day) == ticker.upper():
                return _hide_future_listing(s, day)
        return None

    def prices_as_of(
        self, security_ids: list[str], start: date, as_of: datetime | None, max_rows: int = 50_000
    ) -> list[PriceRow]:
        t_last = self.last_session_index(require_as_of(as_of))
        if t_last < 0:
            return []
        ds = self.dataset
        t_first = int(np.searchsorted(ds.trading_days, np.datetime64(start, "D")))
        rows: list[PriceRow] = []
        for sid in security_ids:
            if sid not in ds.index:
                raise NotFoundError(f"unknown security {sid}")
            i = ds.index[sid]
            for t in range(t_first, t_last + 1):
                close = ds.raw_close[t, i]
                if np.isnan(close):
                    continue
                r = ds.adjusted_returns[t, i]
                rows.append(
                    PriceRow(
                        sid,
                        ds.day(t),
                        float(close),
                        float(ds.split_ratio[t, i]),
                        None if np.isnan(r) else float(r),
                    )
                )
                if len(rows) > max_rows:
                    raise InvalidInputError(f"query exceeds {max_rows} rows; narrow the date range")
        return rows

    def view_as_of(self, as_of: datetime | None) -> MarketDataset:
        """The whole dataset as it was knowable at ``as_of``: the input to a backtest."""
        ts = require_as_of(as_of)
        t_last = self.last_session_index(ts)
        if t_last < 0:
            raise AsOfRequiredError("as_of precedes the first session in the dataset")
        ds = self.dataset
        last_day = ds.day(t_last)
        securities = tuple(_hide_future_listing(s, last_day) for s in ds.securities)
        return MarketDataset(
            dataset_id=ds.dataset_id,
            description=ds.description,
            trading_days=ds.trading_days[: t_last + 1],
            security_ids=ds.security_ids,
            raw_close=ds.raw_close[: t_last + 1].copy(),
            split_ratio=ds.split_ratio[: t_last + 1].copy(),
            securities=securities,
            filings=tuple(f for f in ds.filings if f.accepted_at <= ts),
            prices_simulated=ds.prices_simulated,
            planted={"as_of": ts.isoformat(), "source_dataset_hash": ds.content_hash},
        )
