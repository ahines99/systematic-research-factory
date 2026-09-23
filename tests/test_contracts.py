"""RSF-006, RSF-007: contracts, validators, experiment identity, freezing."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from research_factory.domain.errors import HypothesisFrozenError
from research_factory.domain.identity import canonical_json, content_id
from research_factory.domain.models import AuditEvent, EvidenceRef, Finding, Severity
from research_factory.domain.project_models import BacktestSpec, Experiment, Hypothesis
from research_factory.services.ledger import ResearchLedger

from .conftest import make_experiment


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_experiment(as_of=datetime(2023, 12, 30))


def test_datetimes_are_normalized_to_utc() -> None:
    from zoneinfo import ZoneInfo

    exp = make_experiment(as_of=datetime(2023, 12, 30, 9, 0, tzinfo=ZoneInfo("America/New_York")))
    assert exp.backtest.as_of.tzinfo == UTC
    assert exp.backtest.as_of.hour == 14


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"hold": 0}, "greater than 0"),
        ({"cost": -1.0}, "greater than or equal to 0"),
        ({"delay": -5}, "greater than or equal to 0"),
        ({"end": date(2019, 1, 1)}, "end must be after start"),
        ({"as_of": datetime(2020, 1, 1, tzinfo=UTC)}, "as_of must not be earlier"),
    ],
)
def test_backtest_validators(kwargs: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        make_experiment(**kwargs)


def test_hypothesis_ids_are_slugs() -> None:
    with pytest.raises(ValidationError):
        make_experiment(hypothesis_id="Has Spaces")


def test_experiment_requires_matching_hypothesis_id() -> None:
    exp = make_experiment()
    other = exp.backtest.model_copy(update={"hypothesis_id": "other"})
    with pytest.raises(ValidationError, match="must match"):
        Experiment(hypothesis=exp.hypothesis, backtest=other)


def test_models_are_frozen() -> None:
    exp = make_experiment()
    with pytest.raises(ValidationError):
        exp.hypothesis.statement = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        exp.backtest.transaction_cost_bps = 0.0  # type: ignore[misc]


def test_experiment_id_is_stable_and_content_derived() -> None:
    a, b = make_experiment(), make_experiment()
    assert a.experiment_id == b.experiment_id
    assert a.experiment_id.startswith("exp_")
    assert make_experiment(cost=6.0).experiment_id != a.experiment_id
    assert (
        make_experiment(rationale="A different but still sufficiently long rationale text.").experiment_id
        != a.experiment_id
    )


def test_every_contract_has_a_schema_version() -> None:
    for model in (Hypothesis, BacktestSpec, EvidenceRef, Finding, AuditEvent):
        assert "schema_version" in model.model_fields


def test_canonical_json_is_order_independent_and_rejects_nan() -> None:
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"x": float("nan")})
    assert content_id("x", {"a": 1}) == content_id("x", {"a": 1})


def test_severity_ranks() -> None:
    assert Severity.BLOCKING.rank > Severity.HIGH.rank > Severity.INFO.rank


def test_freeze_is_idempotent_and_changes_create_new_trials(services) -> None:
    ledger: ResearchLedger = services.ledger
    rec1, created1 = ledger.freeze(make_experiment(), "alice")
    rec1b, created1b = ledger.freeze(make_experiment(), "alice")
    rec2, created2 = ledger.freeze(make_experiment(cost=7.0), "alice")
    assert created1 and not created1b and created2
    assert rec1.experiment_id == rec1b.experiment_id
    assert (rec1.trial_number, rec2.trial_number) == (1, 2)
    assert ledger.trial_count("earnings-drift") == 2


def test_presenting_a_modified_document_under_a_frozen_id_is_rejected(services) -> None:
    rec, _ = services.ledger.freeze(make_experiment(), "alice")
    doc = rec.experiment.model_dump(mode="json", exclude={"experiment_id"})
    services.ledger.verify(rec.experiment_id, doc)
    doc["backtest"]["transaction_cost_bps"] = 0.0
    with pytest.raises(HypothesisFrozenError):
        services.ledger.verify(rec.experiment_id, doc)


def test_ledger_has_no_update_path(services) -> None:
    repo = services.repos.experiments
    assert not any(
        name.startswith(("update", "delete", "set")) for name in dir(repo) if not name.startswith("_")
    )
