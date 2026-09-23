"""RSF-008, RSF-009, RSF-016: synthetic fixtures and point-in-time access."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import numpy as np
import pytest

from research_factory.data.calendar import EASTERN, close_utc, execution_lag_sessions, first_close_at_or_after
from research_factory.data.fundamentals import FilingIndex, yoy_change
from research_factory.data.pit import PointInTimeData
from research_factory.data.registry import get_dataset
from research_factory.data.synthetic import generate_synthetic_world
from research_factory.data.world import MarketDataset
from research_factory.domain.errors import AsOfRequiredError

AS_OF = datetime(2023, 12, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def world() -> MarketDataset:
    return get_dataset("synthetic:v1")


def test_generator_is_byte_deterministic() -> None:
    a = generate_synthetic_world(seed=11)
    b = generate_synthetic_world(seed=11)
    assert a.to_bytes() == b.to_bytes()
    assert a.content_hash == b.content_hash
    assert generate_synthetic_world(seed=12).content_hash != a.content_hash


def test_serialization_round_trip(world: MarketDataset) -> None:
    again = MarketDataset.from_bytes(world.to_bytes())
    assert again.content_hash == world.content_hash
    np.testing.assert_array_equal(again.raw_close, world.raw_close)


def test_planted_effects_are_documented(world: MarketDataset) -> None:
    p = world.planted
    assert len(p["delisted"]) == 6 and len(p["ipos"]) == 5
    assert p["ticker_reuse"]["ticker"]
    assert len(p["restatement_accessions"]) >= 5
    assert p["after_close_filings"] > 100
    assert {"period_end", "latest_restated", "current_constituents"} <= set(p["leak_variants"])
    assert 0.2 < p["expected_event_ic"] < 0.35
    assert len(p["splits"]) == 3


def test_restatements_are_amendments_accepted_later(world: MarketDataset) -> None:
    idx = FilingIndex(world.filings)
    for acc in world.planted["restatement_accessions"]:
        amendment = idx.by_accession[acc]
        original = idx.by_accession[amendment.amends]  # type: ignore[index]
        assert amendment.form.endswith("/A")
        assert amendment.accepted_at > original.accepted_at + timedelta(days=50)
        assert amendment.fiscal_period == original.fiscal_period


def test_splits_do_not_move_adjusted_returns(world: MarketDataset) -> None:
    for split in world.planted["splits"]:
        i = world.index[split["security_id"]]
        t = world.session_index(date.fromisoformat(split["session"]))
        raw_move = world.raw_close[t, i] / world.raw_close[t - 1, i] - 1
        assert raw_move < -0.3  # raw price roughly halves
        assert abs(world.adjusted_returns[t, i]) < 0.3


def test_planted_event_ic_is_recovered(world: MarketDataset) -> None:
    """RSF-019: the measured event IC matches the generator's analytic value."""
    p = world.planted
    idx = FilingIndex(world.filings)
    h = p["params"]["drift_days"]
    r = np.nan_to_num(world.adjusted_returns)
    zs, fwd = [], []
    for f in world.filings:
        if f.is_amendment:
            continue
        prior = idx.version_known_at(f.security_id, FilingIndex.year_ago(f.fiscal_period), f.accepted_at)
        a = first_close_at_or_after(world.closes, f.accepted_at)
        if prior is None or a <= 0 or a + h >= len(r):
            continue
        z = np.clip((yoy_change(f.eps, prior.eps) - p["feature_mean"]) / p["feature_std"], -3, 3)
        zs.append(z)
        fwd.append(np.prod(1 + r[a + 1 : a + 1 + h, world.index[f.security_id]]) - 1)
    measured = float(np.corrcoef(zs, fwd)[0, 1])
    assert measured == pytest.approx(p["expected_event_ic"], abs=0.06)


def test_calendar_close_and_lag() -> None:
    assert close_utc(date(2024, 1, 2)).hour == 21  # EST
    assert close_utc(date(2024, 7, 2)).hour == 20  # EDT
    assert execution_lag_sessions(0) == 0
    assert execution_lag_sessions(1) == 1
    assert execution_lag_sessions(390) == 1
    assert execution_lag_sessions(391) == 2


def test_after_close_filings_are_tradable_next_session(world: MarketDataset) -> None:
    late = next(f for f in world.filings if f.accepted_at.astimezone(EASTERN).time() >= time(16, 0))
    t = first_close_at_or_after(world.closes, late.accepted_at)
    assert world.day(t) > late.accepted_at.astimezone(EASTERN).date()


# ----------------------------------------------------------------------- point in time


def test_as_of_is_required_and_must_be_aware(world: MarketDataset) -> None:
    pit = PointInTimeData(world)
    with pytest.raises(AsOfRequiredError):
        pit.filings_as_of(None)
    with pytest.raises(AsOfRequiredError):
        pit.filings_as_of(datetime(2022, 1, 1))  # naive


def test_filings_never_later_than_as_of(world: MarketDataset) -> None:
    pit = PointInTimeData(world)
    as_of = datetime(2021, 5, 3, 20, 0, tzinfo=UTC)
    rows = pit.filings_as_of(as_of)
    assert rows and all(f.accepted_at <= as_of for f in rows)
    assert len(rows) < len(world.filings)


def test_prices_stop_at_last_close_before_as_of(world: MarketDataset) -> None:
    pit = PointInTimeData(world)
    as_of = close_utc(date(2022, 3, 15)) - timedelta(minutes=1)  # one minute before that close
    rows = pit.prices_as_of([world.security_ids[1]], date(2022, 3, 1), as_of)
    assert max(r.session for r in rows) == date(2022, 3, 14)


def test_universe_hides_future_delistings(world: MarketDataset) -> None:
    pit = PointInTimeData(world)
    delisted = next(s for s in world.securities if s.listed_to is not None)
    before = delisted.listed_to - timedelta(days=30)  # type: ignore[operator]
    universe = pit.universe_as_of(datetime.combine(before, time(23, 0), tzinfo=UTC))
    visible = next(s for s in universe if s.security_id == delisted.security_id)
    assert visible.listed_to is None and visible.delisting_return is None


def test_ticker_resolution_depends_on_date(world: MarketDataset) -> None:
    reuse = world.planted["ticker_reuse"]
    pit = PointInTimeData(world)
    first = next(s for s in world.securities if s.security_id == reuse["first_security"])
    second = next(s for s in world.securities if s.security_id == reuse["second_security"])
    early = datetime.combine(first.listed_to - timedelta(days=10), time(23), tzinfo=UTC)  # type: ignore[operator]
    late = datetime.combine(second.listed_from + timedelta(days=10), time(23), tzinfo=UTC)
    assert pit.resolve_ticker(reuse["ticker"], early).security_id == first.security_id  # type: ignore[union-attr]
    assert pit.resolve_ticker(reuse["ticker"], late).security_id == second.security_id  # type: ignore[union-attr]


def test_view_as_of_truncates_everything(world: MarketDataset) -> None:
    as_of = datetime(2021, 6, 30, 23, 0, tzinfo=UTC)
    view = PointInTimeData(world).view_as_of(as_of)
    assert view.day(len(view.trading_days) - 1) <= as_of.date()
    assert all(f.accepted_at <= as_of for f in view.filings)
    assert all(s.listed_to is None or s.listed_to <= as_of.date() for s in view.securities)
