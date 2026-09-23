from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pytest

from research_factory.config import Settings
from research_factory.data.calendar import trading_days
from research_factory.data.world import MarketDataset, Security, TickerInterval
from research_factory.domain.clock import FixedClock
from research_factory.domain.project_models import (
    BacktestSpec,
    Experiment,
    FeatureSpec,
    Hypothesis,
    UniverseSpec,
)
from research_factory.services.container import Services, build_services

RATIONALE = (
    "Investors under-react to earnings news, so prices drift in the direction of the surprise "
    "for weeks after the filing is accepted."
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2024, 1, 2, 12, 0, tzinfo=UTC), step=timedelta(milliseconds=1))


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url="sqlite://", blob_store="memory://", model_provider="rules")


@pytest.fixture
def services(settings: Settings, clock: FixedClock) -> Services:
    return build_services(settings, clock=clock)


def make_experiment(
    *,
    hypothesis_id: str = "eps-drift",
    family: str = "earnings-drift",
    feature: str = "eps_yoy_change",
    timing: str = "acceptance",
    dataset: str = "synthetic:v1",
    mode: str = "point_in_time",
    delay: int = 30,
    cost: float = 5.0,
    hold: int = 20,
    rationale: str = RATIONALE,
    statement: str = "Companies with rising EPS keep outperforming after the filing is public.",
    **backtest: Any,
) -> Experiment:
    h = Hypothesis(
        hypothesis_id=hypothesis_id,
        research_family=family,
        statement=statement,
        rationale=rationale,
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        feature=FeatureSpec(name=feature, timing_basis=timing),  # type: ignore[arg-type]
        universe=UniverseSpec(dataset=dataset, mode=mode),  # type: ignore[arg-type]
        horizon_days=hold,
    )
    b = BacktestSpec(
        hypothesis_id=hypothesis_id,
        start=backtest.pop("start", date(2019, 6, 3)),
        end=backtest.pop("end", date(2023, 12, 29)),
        as_of=backtest.pop("as_of", datetime(2023, 12, 30, tzinfo=UTC)),
        execution_delay_minutes=delay,
        transaction_cost_bps=cost,
        hold_days=hold,
        **backtest,
    )
    return Experiment(hypothesis=h, backtest=b)


@pytest.fixture
def experiment_factory() -> Callable[..., Experiment]:
    return make_experiment


def tiny_dataset(
    returns: np.ndarray, start: date = date(2024, 1, 1), listed_to: dict[int, int] | None = None
) -> MarketDataset:
    """A dataset built directly from a returns matrix (row 0 is ignored: prices start at 100)."""
    t_count, n = returns.shape
    days = trading_days(start, start + timedelta(days=t_count * 2 + 10))[:t_count]
    listed_to = listed_to or {}
    closes = np.full((t_count, n), np.nan)
    for i in range(n):
        last = listed_to.get(i, t_count - 1)
        closes[0, i] = 100.0
        for t in range(1, last + 1):
            closes[t, i] = closes[t - 1, i] * (1 + returns[t, i])
    securities = tuple(
        Security(
            security_id=f"S{i}",
            name=f"Test {i}",
            listed_from=days[0].item(),
            listed_to=days[listed_to[i]].item() if i in listed_to else None,
            tickers=(TickerInterval(f"T{i}", days[0].item(), None),),
        )
        for i in range(n)
    )
    return MarketDataset(
        dataset_id="tiny",
        description="test",
        trading_days=days,
        security_ids=tuple(s.security_id for s in securities),
        raw_close=closes,
        split_ratio=np.ones((t_count, n)),
        securities=securities,
        filings=(),
        prices_simulated=True,
    )
