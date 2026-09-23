"""The primary research workflow: nine steps, in order."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..domain.errors import ConflictError
from ..domain.project_models import WorkflowRun
from .base import Step
from .engine import WorkflowEngine
from .steps import (
    BacktestStep,
    DataAcquisitionStep,
    EconomicRationaleStep,
    FeatureBuildStep,
    HypothesisFreezeStep,
    ImplementationReviewStep,
    LeakageAuditStep,
    ResearchCommitteeStep,
    StatisticalReviewStep,
)

if TYPE_CHECKING:
    from ..services.container import Services


def primary_steps() -> list[Step]:
    return [
        HypothesisFreezeStep(),
        DataAcquisitionStep(),
        FeatureBuildStep(),
        BacktestStep(),
        LeakageAuditStep(),
        StatisticalReviewStep(),
        EconomicRationaleStep(),
        ImplementationReviewStep(),
        ResearchCommitteeStep(),
    ]


PROJECT_STEPS = [s.name for s in primary_steps()]


def primary_engine(services: Services) -> WorkflowEngine:
    return WorkflowEngine(services, primary_steps())


# Standalone analysis tools run the deterministic prefix of the workflow.
ANALYSIS_STEPS = {"build_features": 3, "run_backtest": 4, "audit_leakage": 5, "get_statistics": 6}


def engine_for_run(services: Services, run: WorkflowRun) -> WorkflowEngine:
    """The engine a paused run must be resumed with, so resuming never changes a run's shape."""
    if run.project_type == "systematic_research":
        return primary_engine(services)
    if run.project_type.startswith("analysis:"):
        tool = run.project_type.split(":", 1)[1]
        if tool in ANALYSIS_STEPS:
            return WorkflowEngine(services, primary_steps()[: ANALYSIS_STEPS[tool]])
    raise ConflictError(f"runs of type {run.project_type!r} cannot be resumed; start a new one")
