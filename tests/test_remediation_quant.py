"""Regression proofs for A05/A08/A09 and the adjacent data integrity boundaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pytest

from research_factory.config import StatisticalThresholds
from research_factory.data.calendar import EASTERN, close_utc, first_close_at_or_after
from research_factory.data.pit import PointInTimeData
from research_factory.data.registry import get_dataset
from research_factory.data.world import MarketDataset, filing_to_dict
from research_factory.domain.errors import NeedsEvidenceError
from research_factory.domain.project_models import BacktestSpec, TimingBasis, UniverseMode
from research_factory.research.backtest import run_backtest
from research_factory.research.features import FeatureTable, build_features, rebalance_sessions
from research_factory.research.leakage import (
    audit_leakage,
    check_lineage_complete,
    check_lineage_semantics,
    check_values_reproduce,
    recompute,
)
from research_factory.research.quality import check_dataset, validate_backtest_coverage
from research_factory.research.statistics import block_bootstrap_sharpe_ci, statistical_review
from research_factory.services.container import Services
from research_factory.workflows.primary import primary_engine

from .conftest import make_experiment, tiny_dataset


@pytest.fixture(scope="module")
def view() -> MarketDataset:
    return PointInTimeData(get_dataset("synthetic:v1")).view_as_of(datetime(2023, 12, 30, tzinfo=UTC))


def _table(view: MarketDataset, feature: str = "momentum_60_5", hold: int = 20) -> FeatureTable:
    spec = make_experiment(hold=hold).backtest
    return build_features(
        view,
        feature=feature,
        timing_basis=TimingBasis.ACCEPTANCE,
        universe_mode=UniverseMode.POINT_IN_TIME,
        sessions=rebalance_sessions(view, spec.start, spec.end, hold),
        filings_evidence_id="filings",
        prices_evidence_id="prices",
    )


def _spec(ds: MarketDataset, **kwargs: Any) -> BacktestSpec:
    return make_experiment(
        start=ds.day(0),
        end=ds.day(len(ds.trading_days) - 1),
        as_of=datetime(2030, 1, 1, tzinfo=UTC),
        **kwargs,
    ).backtest


def _tiny_table(ds: MarketDataset, sessions: list[int], values: list[list[float]]) -> FeatureTable:
    return FeatureTable(
        "test",
        TimingBasis.ACCEPTANCE,
        UniverseMode.POINT_IN_TIME,
        sessions,
        ds.security_ids,
        np.array(values),
        ds.listed_mask[sessions],
    )


@pytest.mark.parametrize(
    ("start", "end"), [(date(2010, 1, 1), date(2023, 12, 29)), (date(2019, 6, 3), date(2025, 12, 31))]
)
def test_a05_frozen_window_cannot_be_silently_clipped(view: MarketDataset, start: date, end: date) -> None:
    spec = make_experiment(start=start, end=end, as_of=datetime(2026, 1, 1, tzinfo=UTC)).backtest
    with pytest.raises(NeedsEvidenceError, match="frozen backtest range"):
        validate_backtest_coverage(view, spec)
    with pytest.raises(NeedsEvidenceError, match="frozen backtest range"):
        run_backtest(view, _table(view), spec)


def test_a05_weekend_endpoints_are_valid_but_missing_final_close_is_not(view: MarketDataset) -> None:
    spec = make_experiment(
        start=date(2019, 6, 1), end=date(2023, 12, 31), as_of=datetime(2024, 1, 1, tzinfo=UTC)
    ).backtest
    validate_backtest_coverage(view, spec)
    early = make_experiment(as_of=close_utc(date(2023, 12, 29)) - timedelta(microseconds=1)).backtest
    with pytest.raises(NeedsEvidenceError):
        validate_backtest_coverage(view, early)


def test_a05_internal_missing_session_blocks_coverage(view: MarketDataset) -> None:
    keep = np.arange(len(view.trading_days)) != 500
    incomplete = replace(
        view,
        trading_days=view.trading_days[keep],
        raw_close=view.raw_close[keep],
        split_ratio=view.split_ratio[keep],
    )
    with pytest.raises(NeedsEvidenceError):
        validate_backtest_coverage(incomplete, make_experiment().backtest)


@pytest.mark.anyio
async def test_a05_workflow_pauses_before_computing_shortened_sample(services: Services) -> None:
    exp = make_experiment(end=date(2025, 12, 31), as_of=datetime(2026, 1, 1, tzinfo=UTC))
    services.ledger.freeze(exp, "researcher")
    run = await primary_engine(services).start(exp.experiment_id, "researcher")
    assert run.current_step == "Data acquisition"
    assert "NEEDS_EVIDENCE" in (run.status_reason or "")
    assert services.repos.steps.get(run.run_id, "Backtest") is None


@pytest.mark.anyio
async def test_nonfinite_fundamentals_pause_before_snapshot_serialization(
    services: Services, monkeypatch: pytest.MonkeyPatch, view: MarketDataset
) -> None:
    invalid = replace(view, filings=(replace(view.filings[0], eps=float("nan")), *view.filings[1:]))
    monkeypatch.setattr(Services, "dataset", lambda _self, _name: invalid)
    exp = make_experiment()
    services.ledger.freeze(exp, "researcher")
    run = await primary_engine(services).start(exp.experiment_id, "researcher")
    assert run.current_step == "Data acquisition"
    assert "NEEDS_EVIDENCE" in (run.status_reason or "")
    assert services.repos.steps.get(run.run_id, "Feature build") is None


def _set_value(doc: dict[str, Any], row: dict[str, Any], value: float) -> None:
    row["value"] = value
    day = datetime.fromisoformat(row["decision_ts"]).astimezone(EASTERN).date().isoformat()
    doc["values"][doc["sessions"].index(day)][doc["security_ids"].index(row["security_id"])] = value


def test_a08_nan_recomputation_cannot_approve_arbitrary_value(view: MarketDataset) -> None:
    table = _table(view)
    doc = deepcopy(table.to_document(view))
    ipo = next(s for s in view.securities if s.listed_from > view.day(3))
    row = next(r for r in doc["lineage"]["rows"] if r["security_id"] == ipo.security_id)
    _set_value(doc, row, 123456789.0)
    for inp, t in zip(row["inputs"], [0, 1], strict=True):
        inp["locator"] = f"price:{ipo.security_id}:{view.day(t)}"
        inp["knowledge_ts"] = close_utc(view.day(t)).isoformat()
    assert np.isnan(recompute(doc["feature"], row, {}, view))
    report = audit_leakage(
        feature_doc=doc,
        backtest_doc=run_backtest(view, table, make_experiment().backtest).to_document(view),
        filings_doc=[filing_to_dict(f) for f in view.filings],
        dataset=view,
        input_sources=frozenset({"price"}),
    )
    checks = {c.check: c for c in report.checks}
    assert report.blocking
    assert not checks["values_reproduce"].passed
    assert not checks["lineage_semantics"].passed
    assert checks["values_reproduce"].examples[0]["recomputed"] is None


@pytest.mark.parametrize("change", ["security", "window", "reversed", "decision", "naive"])
def test_a08_price_lineage_binds_exact_security_window_and_close(view: MarketDataset, change: str) -> None:
    doc = deepcopy(_table(view).to_document(view))
    row = doc["lineage"]["rows"][0]
    if change == "security":
        row["inputs"][0]["locator"] = row["inputs"][0]["locator"].replace(row["security_id"], "unrelated")
    elif change == "window":
        row["inputs"][0]["locator"] = row["inputs"][1]["locator"]
    elif change == "reversed":
        row["inputs"].reverse()
    elif change == "decision":
        row["decision_ts"] = (datetime.fromisoformat(row["decision_ts"]) + timedelta(hours=1)).isoformat()
    else:
        row["decision_ts"] = datetime.fromisoformat(row["decision_ts"]).replace(tzinfo=None).isoformat()
    check = check_lineage_semantics(doc, [filing_to_dict(f) for f in view.filings], view)
    assert not check.passed and check.violations == 1


def test_a08_eps_requires_correct_known_security_period_and_version(view: MarketDataset) -> None:
    doc = deepcopy(_table(view, "eps_yoy_change").to_document(view))
    row = doc["lineage"]["rows"][0]
    # Reuse the current filing as the year-ago input; numerically reproducible, semantically wrong.
    row["inputs"][1] = deepcopy(row["inputs"][0])
    _set_value(doc, row, 0.0)
    filings = [filing_to_dict(f) for f in view.filings]
    assert check_values_reproduce(doc, filings, view).passed
    assert not check_lineage_semantics(doc, filings, view).passed


@pytest.mark.parametrize("change", ["orphan", "duplicate", "nan", "inf"])
def test_a08_lineage_rejects_extra_rows_and_nonfinite_values(view: MarketDataset, change: str) -> None:
    doc = deepcopy(_table(view).to_document(view))
    row = doc["lineage"]["rows"][0]
    if change == "orphan":
        orphan = deepcopy(row)
        orphan["security_id"] = "unrelated"
        doc["lineage"]["rows"].append(orphan)
    elif change == "duplicate":
        doc["lineage"]["rows"].append(deepcopy(row))
    else:
        _set_value(doc, row, float(change))
    assert not check_lineage_complete(doc).passed


def test_a09_delisting_between_decision_and_execution_cancels_without_reranking() -> None:
    ds = tiny_dataset(np.zeros((8, 4)), listed_to={3: 1})
    table = _tiny_table(ds, [1], [[4.0, 2.0, 1.0, 0.0]])
    bt = run_backtest(ds, table, _spec(ds, hold=10, cost=10.0, quantile=0.25))
    assert bt.positions[0]["short"] == [] and bt.positions[0]["long"] == ["S0"]
    assert bt.unfilled_orders == [
        {
            "decision": "2024-01-02",
            "execution": "2024-01-03",
            "security_id": "S3",
            "requested_weight": -0.5,
            "reason": "not_listed",
        }
    ]
    assert bt.turnover[0]["turnover"] == 0.5
    assert bt.net[0] == pytest.approx(-0.0005)
    assert "S3" in bt.universe_by_decision[0]["universe"]


def test_a09_settled_delisting_does_not_charge_a_phantom_closing_trade() -> None:
    returns = np.zeros((8, 4))
    returns[3, 3] = -0.5
    ds = tiny_dataset(returns, listed_to={3: 3})
    table = _tiny_table(ds, [1, 4], [[0.0, 1.0, 2.0, 4.0], [0.0, 1.0, 2.0, 4.0]])
    bt = run_backtest(ds, table, _spec(ds, hold=3, cost=10.0, quantile=0.25))
    assert bt.gross[bt.sessions.index(3)] == pytest.approx(-0.25)
    assert [t["turnover"] for t in bt.turnover] == [1.0, 0.5]


@pytest.mark.parametrize(("name", "count"), [("synthetic:v1", 1), ("edgar-semi:v1", 6)])
def test_a09_daily_builtin_strategies_never_fill_delisted_names(name: str, count: int) -> None:
    ds = PointInTimeData(get_dataset(name)).view_as_of(datetime(2023, 12, 30, tzinfo=UTC))
    bt = run_backtest(ds, _table(ds, feature="eps_yoy_change", hold=1), make_experiment(hold=1).backtest)
    assert len([o for o in bt.unfilled_orders if o["requested_weight"] != 0]) == count
    for position in bt.positions:
        for sid in position["long"] + position["short"]:
            assert ds.securities[ds.index[sid]].is_listed(date.fromisoformat(position["execution"]))


@pytest.mark.parametrize("kind", ["price_inf", "split_inf", "split_nan", "split_zero", "eps_inf"])
def test_numeric_quality_blocks_nonfinite_data(view: MarketDataset, kind: str) -> None:
    if kind == "eps_inf":
        broken = replace(view, filings=(replace(view.filings[0], eps=float("inf")), *view.filings[1:]))
    elif kind == "price_inf":
        raw = view.raw_close.copy()
        raw[100, 0] = np.inf
        broken = replace(view, raw_close=raw)
    else:
        splits = view.split_ratio.copy()
        splits[100, 0] = {"split_inf": np.inf, "split_nan": np.nan, "split_zero": 0.0}[kind]
        broken = replace(view, split_ratio=splits)
    assert any(i.blocking for i in check_dataset(broken))


def test_dataset_cached_buffers_and_metadata_cannot_change_after_hash(view: MarketDataset) -> None:
    identity, document = view.content_hash, view.to_bytes()
    for array in [
        view.raw_close,
        view.split_ratio,
        view.trading_days,
        view.adjusted_returns,
        view.listed_mask,
        view.closes,
    ]:
        with pytest.raises(ValueError, match="WRITEABLE"):
            array.setflags(write=True)
        with pytest.raises(ValueError, match="read-only"):
            array.flat[0] = 0
    with pytest.raises(TypeError):
        view.planted["changed"] = True  # type: ignore[index]
    exported = view.to_document()
    exported["planted"]["changed"] = True
    assert view.content_hash == identity and view.to_bytes() == document


def test_dataset_detaches_from_input_arrays_and_nested_metadata() -> None:
    ds = tiny_dataset(np.zeros((8, 4)))
    raw = ds.raw_close.copy()
    metadata = {"nested": [{"value": 1}]}
    frozen = replace(ds, raw_close=raw, planted=metadata)
    identity = frozen.content_hash
    raw[0, 0] = 0
    metadata["nested"][0]["value"] = 2
    assert frozen.raw_close[0, 0] == 100 and frozen.planted["nested"][0]["value"] == 1
    assert frozen.content_hash == identity


def test_subsecond_acceptance_after_close_maps_to_next_session(view: MarketDataset) -> None:
    assert first_close_at_or_after(view.closes, close_utc(view.day(0)) + timedelta(microseconds=1)) == 1


def test_s2_bootstrap_artifact_metadata_reproduces_the_reported_interval() -> None:
    returns = np.random.default_rng(11).normal(0.001, 0.01, 40)
    report = statistical_review(
        returns,
        returns,
        hold_days=60,
        ic_values=[],
        turnover=[],
        trial_sharpes=[],
        n_trials=1,
        thresholds=StatisticalThresholds(bootstrap_samples=100, bootstrap_confidence=0.9),
    ).to_document()
    assert report["bootstrap_method"] == "circular_block"
    assert report["bootstrap_interval_method"] == "percentile"
    assert report["bootstrap_block_size"] == len(returns)
    assert report["bootstrap_samples"] == 100
    interval = block_bootstrap_sharpe_ci(
        returns,
        report["bootstrap_block_size"],
        report["bootstrap_samples"],
        report["bootstrap_confidence"],
        report["bootstrap_seed"],
    )
    assert list(interval) == report["bootstrap_ci"]
    assert report["var_sr_source"] and report["newey_west_lags"] == 60
