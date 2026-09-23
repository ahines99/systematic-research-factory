"""``sec_pit`` and ``market_data_pit`` capability modules: point-in-time data reads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import BaseModel, Field

from ..data.pit import PointInTimeData, require_as_of
from ..data.registry import dataset_names, get_dataset
from ..data.world import filing_to_dict
from ..domain.errors import NotFoundError
from .common import ServerDeps, governed

MAX_SECURITIES = 25


class FilingRecord(BaseModel):
    accession: str
    security_id: str
    form: str
    fiscal_period: str
    period_end: str
    filed_date: str
    accepted_at: str
    eps: float
    amends: str | None


class FilingsResult(BaseModel):
    dataset: str
    as_of: str
    evidence_id: str
    count: int
    filings: list[FilingRecord]


class PriceRecord(BaseModel):
    security_id: str
    session: str
    raw_close: float
    split_ratio: float
    adjusted_return: float | None


class PricesResult(BaseModel):
    dataset: str
    as_of: str
    evidence_id: str
    prices_simulated: bool
    count: int
    prices: list[PriceRecord]


class SecurityRecord(BaseModel):
    security_id: str
    name: str
    ticker: str | None
    listed_from: str
    listed_to: str | None


class UniverseResult(BaseModel):
    dataset: str
    as_of: str
    evidence_id: str
    count: int
    securities: list[SecurityRecord]


def _record(deps: ServerDeps, value: Any, *, dataset: str, kind: str, as_of: datetime) -> str:
    ref = deps.services.evidence.record_json(
        value, source_uri=f"rsf://datasets/{dataset}/{kind}", source_type=f"query:{kind}", as_of=as_of
    )
    return ref.evidence_id


def _pit(dataset: str) -> PointInTimeData:
    if dataset not in dataset_names():
        raise NotFoundError(f"unknown dataset {dataset!r}; known: {dataset_names()}")
    return PointInTimeData(get_dataset(dataset))


def register(mcp: MCPServer, deps: ServerDeps) -> None:
    @mcp.tool(
        description="Filings (with EPS) known at `as_of` for one security. Knowledge time is SEC acceptance."
    )
    async def get_filings_as_of(
        security_id: str,
        as_of: datetime | None = None,
        dataset: str = "edgar-semi:v1",
        form: str | None = None,
        ctx: Context[Any, Any] | None = None,
    ) -> FilingsResult:
        async def body(_: Any) -> FilingsResult:
            ts = require_as_of(as_of)
            rows = _pit(dataset).filings_as_of(ts, {security_id}, form)
            docs = [filing_to_dict(f) for f in rows]
            ev = _record(
                deps, {"security_id": security_id, "filings": docs}, dataset=dataset, kind="filings", as_of=ts
            )
            return FilingsResult(
                dataset=dataset,
                as_of=ts.isoformat(),
                evidence_id=ev,
                count=len(docs),
                filings=[FilingRecord(**d) for d in docs],
            )

        return await governed(
            deps,
            ctx,
            "get_filings_as_of",
            "read_data",
            {"security_id": security_id, "as_of": str(as_of), "dataset": dataset},
            body,
        )

    @mcp.tool(
        description="Daily closes known at `as_of` (a session's close is known at 16:00 ET). Prices are simulated."
    )
    async def get_prices_as_of(
        security_ids: list[str] = Field(min_length=1, max_length=MAX_SECURITIES),
        start: date = Field(description="First session to return"),
        as_of: datetime | None = None,
        dataset: str = "edgar-semi:v1",
        ctx: Context[Any, Any] | None = None,
    ) -> PricesResult:
        async def body(_: Any) -> PricesResult:
            ts = require_as_of(as_of)
            pit = _pit(dataset)
            rows = [r.to_dict() for r in pit.prices_as_of(security_ids, start, ts)]
            ev = _record(
                deps,
                {"security_ids": security_ids, "start": start.isoformat(), "rows": rows},
                dataset=dataset,
                kind="prices",
                as_of=ts,
            )
            return PricesResult(
                dataset=dataset,
                as_of=ts.isoformat(),
                evidence_id=ev,
                count=len(rows),
                prices_simulated=pit.dataset.prices_simulated,
                prices=[PriceRecord(**r) for r in rows],
            )

        return await governed(
            deps,
            ctx,
            "get_prices_as_of",
            "read_data",
            {"security_ids": security_ids, "start": str(start), "as_of": str(as_of)},
            body,
        )

    @mcp.tool(
        description="Securities listed at `as_of`, including names that later delisted. Future delistings are hidden."
    )
    async def get_universe_as_of(
        as_of: datetime | None = None,
        dataset: str = "edgar-semi:v1",
        ctx: Context[Any, Any] | None = None,
    ) -> UniverseResult:
        async def body(_: Any) -> UniverseResult:
            ts = require_as_of(as_of)
            pit = _pit(dataset)
            day = pit.dataset.day(max(pit.last_session_index(ts), 0))
            secs = [
                SecurityRecord(
                    security_id=s.security_id,
                    name=s.name,
                    ticker=s.ticker_on(day),
                    listed_from=s.listed_from.isoformat(),
                    listed_to=s.listed_to.isoformat() if s.listed_to else None,
                )
                for s in pit.universe_as_of(ts)
            ]
            ev = _record(deps, [s.model_dump() for s in secs], dataset=dataset, kind="universe", as_of=ts)
            return UniverseResult(
                dataset=dataset, as_of=ts.isoformat(), evidence_id=ev, count=len(secs), securities=secs
            )

        return await governed(
            deps, ctx, "get_universe_as_of", "read_data", {"as_of": str(as_of), "dataset": dataset}, body
        )
