"""Research contracts: hypotheses, backtest specs, experiments, runs, approvals."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from .identity import content_id
from .models import UTCDateTime

SCHEMA_VERSION = "1"


class TimingBasis(StrEnum):
    """When a filing-derived value is treated as known."""

    ACCEPTANCE = "acceptance"  # correct: SEC acceptance datetime
    PERIOD_END = "period_end"  # look-ahead: fiscal period end
    LATEST_RESTATED = "latest_restated"  # look-ahead: final restated value back-filled


class UniverseMode(StrEnum):
    POINT_IN_TIME = "point_in_time"  # correct: membership as of each decision date
    CURRENT_CONSTITUENTS = "current_constituents"  # survivorship bias


class FeatureSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    timing_basis: TimingBasis = TimingBasis.ACCEPTANCE


class UniverseSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    dataset: str = Field(min_length=1, description="Dataset identifier, e.g. 'synthetic:v1'")
    mode: UniverseMode = UniverseMode.POINT_IN_TIME


class Hypothesis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    hypothesis_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    research_family: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    statement: str = Field(min_length=10)
    rationale: str = Field(default="", description="Economic mechanism the researcher expects")
    created_at: UTCDateTime
    feature: FeatureSpec
    universe: UniverseSpec
    horizon_days: int = Field(gt=0, le=252)
    expected_sign: Literal[1, -1] = 1


class BacktestSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    hypothesis_id: str
    start: date
    end: date
    as_of: UTCDateTime = Field(description="Knowledge cutoff: no data known after this instant may be used")
    execution_delay_minutes: int = Field(ge=0)
    transaction_cost_bps: float = Field(ge=0, le=1000)
    hold_days: int = Field(gt=0, le=252)
    quantile: float = Field(default=0.2, gt=0, le=0.5)

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.as_of.date() < self.end:
            raise ValueError("as_of must not be earlier than the backtest end date")
        return self


class Experiment(BaseModel):
    """A frozen hypothesis plus its backtest specification. Identity is content-derived."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hypothesis: Hypothesis
    backtest: BacktestSpec

    @model_validator(mode="after")
    def _check_link(self) -> Self:
        if self.backtest.hypothesis_id != self.hypothesis.hypothesis_id:
            raise ValueError("backtest.hypothesis_id must match hypothesis.hypothesis_id")
        if self.backtest.hold_days != self.hypothesis.horizon_days:
            raise ValueError("backtest.hold_days must equal the frozen hypothesis.horizon_days")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def experiment_id(self) -> str:
        return experiment_id_for(self.hypothesis, self.backtest)


def experiment_id_for(hypothesis: Hypothesis, backtest: BacktestSpec) -> str:
    """Stable content hash: any change to either document yields a new experiment ID."""
    return content_id(
        "exp",
        {"hypothesis": hypothesis.model_dump(mode="json"), "backtest": backtest.model_dump(mode="json")},
    )


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    COMPLETE = "complete"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in (RunStatus.COMPLETE, RunStatus.FAILED)


# Allowed status transitions. Anything else is a bug and is rejected.
RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.RUNNING: frozenset({RunStatus.NEEDS_REVIEW, RunStatus.COMPLETE, RunStatus.FAILED}),
    RunStatus.NEEDS_REVIEW: frozenset({RunStatus.RUNNING, RunStatus.COMPLETE, RunStatus.FAILED}),
    RunStatus.COMPLETE: frozenset(),
    RunStatus.FAILED: frozenset(),
}


class StepStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class WorkflowRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    experiment_id: str
    project_type: str = "systematic_research"
    status: RunStatus
    current_step: str | None = None
    requested_by: str
    decision: ApprovalDecision | None = None
    status_reason: str | None = None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    execution_manifest: dict[str, Any] = Field(default_factory=dict)


class StepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    step: str
    status: StepStatus
    idempotency_key: str
    artifact_evidence_id: str | None = None
    attempts: int = 1
    error_code: str | None = None
    error_message: str | None = None
    created_at: UTCDateTime
    fail_run: bool = False
    run_decision: ApprovalDecision | None = None
    gate_context: str | None = None


class ApprovalRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_id: str
    run_id: str
    step: str
    approver: str
    decision: ApprovalDecision
    reason: str = Field(min_length=3)
    created_at: UTCDateTime
    gate_context: str = "legacy"


class ExperimentRecord(BaseModel):
    """A research-ledger entry. One per frozen experiment; never updated except for its result."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    research_family: str
    trial_number: int
    experiment: Experiment
    created_by: str
    created_at: UTCDateTime
    sharpe_per_period: float | None = None

    @field_validator("trial_number")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("trial_number starts at 1")
        return value


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
