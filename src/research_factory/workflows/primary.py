"""The primary research workflow: nine steps, in order."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
