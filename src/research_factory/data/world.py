"""In-memory research dataset: securities, filings and daily prices.

A ``MarketDataset`` is immutable and serializes to deterministic bytes, so a snapshot
of it can be content-addressed and replayed exactly.
"""

from __future__ import annotations

import base64
import gzip
import io
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import cached_property
from typing import Any

import numpy as np
import numpy.typing as npt

from ..domain.identity import canonical_json, sha256_hex
from .calendar import close_epochs

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class TickerInterval:
    ticker: str
    start: date
    end: date | None  # last day the ticker referred to this security; None = still does


@dataclass(frozen=True, slots=True)
class Security:
    security_id: str  # permanent identifier (CIK for EDGAR data)
    name: str
    listed_from: date
    listed_to: date | None  # last trading session; None = still listed
    tickers: tuple[TickerInterval, ...] = ()
    delisting_return: float | None = None

    def is_listed(self, day: date) -> bool:
        return self.listed_from <= day and (self.listed_to is None or day <= self.listed_to)

    def ticker_on(self, day: date) -> str | None:
        for interval in self.tickers:
            if interval.start <= day and (interval.end is None or day <= interval.end):
                return interval.ticker
        return None


@dataclass(frozen=True, slots=True)
class Filing:
    accession: str
    security_id: str
    form: str
    fiscal_period: str  # "YYYYQn"
    period_end: date
    filed_date: date
    accepted_at: datetime  # UTC; the knowledge time
    eps: float
    amends: str | None = None  # accession of the original filing this amends

    @property
    def is_amendment(self) -> bool:
        return self.amends is not None


def fiscal_period_minus(period: str, quarters: int) -> str:
    year, q = int(period[:4]), int(period[5])
    index = year * 4 + (q - 1) - quarters
    return f"{index // 4}Q{index % 4 + 1}"


def _encode_array(array: FloatArray) -> str:
    data = np.ascontiguousarray(array, dtype="<f8").tobytes()
    return base64.b64encode(data).decode("ascii")


def _decode_array(text: str, shape: tuple[int, ...]) -> FloatArray:
    return np.frombuffer(base64.b64decode(text), dtype="<f8").reshape(shape).copy()


@dataclass(frozen=True)
class MarketDataset:
    dataset_id: str
    description: str
    trading_days: npt.NDArray[np.datetime64]
    security_ids: tuple[str, ...]
    raw_close: FloatArray  # [T, N]; NaN when not listed
    split_ratio: FloatArray  # [T, N]; new shares per old share on the split session, else 1
    securities: tuple[Security, ...]
    filings: tuple[Filing, ...]
    prices_simulated: bool
    planted: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        t, n = len(self.trading_days), len(self.security_ids)
        if self.raw_close.shape != (t, n) or self.split_ratio.shape != (t, n):
            raise ValueError("price arrays must be [sessions, securities]")
        if tuple(s.security_id for s in self.securities) != self.security_ids:
            raise ValueError("securities must be in security_ids order")

    @cached_property
    def closes(self) -> npt.NDArray[np.int64]:
        return close_epochs(self.trading_days)

    @cached_property
    def index(self) -> dict[str, int]:
        return {sid: i for i, sid in enumerate(self.security_ids)}

    @cached_property
    def adjusted_returns(self) -> FloatArray:
        """Split-adjusted close-to-close returns; NaN where either close is missing."""
        prev = self.raw_close[:-1]
        cur = self.raw_close[1:] * self.split_ratio[1:]
        with np.errstate(invalid="ignore", divide="ignore"):
            r = cur / prev - 1.0
        out = np.full_like(self.raw_close, np.nan)
        out[1:] = r
        return out

    @cached_property
    def listed_mask(self) -> npt.NDArray[np.bool_]:
        days = [d.item() for d in self.trading_days]
        return np.array([[s.is_listed(d) for s in self.securities] for d in days], dtype=bool)

    def day(self, t: int) -> date:
        return self.trading_days[t].item()  # type: ignore[no-any-return]

    def session_index(self, day: date) -> int:
        idx = int(np.searchsorted(self.trading_days, np.datetime64(day, "D")))
        if idx >= len(self.trading_days) or self.trading_days[idx] != np.datetime64(day, "D"):
            raise KeyError(f"{day} is not a session")
        return idx

    # --- serialization -------------------------------------------------------------

    def to_document(self) -> dict[str, Any]:
        return {
            "format": "rsf-market-dataset/1",
            "dataset_id": self.dataset_id,
            "description": self.description,
            "prices_simulated": self.prices_simulated,
            "trading_days": [str(d) for d in self.trading_days],
            "security_ids": list(self.security_ids),
            "raw_close": _encode_array(self.raw_close),
            "split_ratio": _encode_array(self.split_ratio),
            "securities": [
                {
                    "security_id": s.security_id,
                    "name": s.name,
                    "listed_from": s.listed_from.isoformat(),
                    "listed_to": s.listed_to.isoformat() if s.listed_to else None,
                    "delisting_return": s.delisting_return,
                    "tickers": [
                        {
                            "ticker": ti.ticker,
                            "start": ti.start.isoformat(),
                            "end": ti.end.isoformat() if ti.end else None,
                        }
                        for ti in s.tickers
                    ],
                }
                for s in self.securities
            ],
            "filings": [filing_to_dict(f) for f in self.filings],
            "planted": self.planted,
        }

    def to_bytes(self) -> bytes:
        """Deterministic gzip of the canonical JSON document (mtime fixed at 0)."""
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0, compresslevel=6) as gz:
            gz.write(canonical_json(self.to_document()))
        return buffer.getvalue()

    @cached_property
    def content_hash(self) -> str:
        return sha256_hex(canonical_json(self.to_document()))

    @classmethod
    def from_document(cls, doc: dict[str, Any]) -> MarketDataset:
        if doc.get("format") != "rsf-market-dataset/1":
            raise ValueError("unsupported dataset format")
        days = np.array(doc["trading_days"], dtype="datetime64[D]")
        ids = tuple(doc["security_ids"])
        shape = (len(days), len(ids))
        securities = tuple(
            Security(
                security_id=s["security_id"],
                name=s["name"],
                listed_from=date.fromisoformat(s["listed_from"]),
                listed_to=date.fromisoformat(s["listed_to"]) if s["listed_to"] else None,
                delisting_return=s["delisting_return"],
                tickers=tuple(
                    TickerInterval(
                        t["ticker"],
                        date.fromisoformat(t["start"]),
                        date.fromisoformat(t["end"]) if t["end"] else None,
                    )
                    for t in s["tickers"]
                ),
            )
            for s in doc["securities"]
        )
        return cls(
            dataset_id=doc["dataset_id"],
            description=doc["description"],
            trading_days=days,
            security_ids=ids,
            raw_close=_decode_array(doc["raw_close"], shape),
            split_ratio=_decode_array(doc["split_ratio"], shape),
            securities=securities,
            filings=tuple(filing_from_dict(f) for f in doc["filings"]),
            prices_simulated=doc["prices_simulated"],
            planted=doc["planted"],
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> MarketDataset:
        import json

        return cls.from_document(json.loads(gzip.decompress(data)))


def filing_to_dict(f: Filing) -> dict[str, Any]:
    return {
        "accession": f.accession,
        "security_id": f.security_id,
        "form": f.form,
        "fiscal_period": f.fiscal_period,
        "period_end": f.period_end.isoformat(),
        "filed_date": f.filed_date.isoformat(),
        "accepted_at": f.accepted_at.astimezone(UTC).isoformat(),
        "eps": f.eps,
        "amends": f.amends,
    }


def filing_from_dict(d: dict[str, Any]) -> Filing:
    accepted = datetime.fromisoformat(d["accepted_at"])
    if accepted.tzinfo is None:
        raise ValueError("accepted_at must be timezone-aware")
    return Filing(
        accession=d["accession"],
        security_id=d["security_id"],
        form=d["form"],
        fiscal_period=d["fiscal_period"],
        period_end=date.fromisoformat(d["period_end"]),
        filed_date=date.fromisoformat(d["filed_date"]),
        accepted_at=accepted.astimezone(UTC),
        eps=float(d["eps"]),
        amends=d.get("amends"),
    )
