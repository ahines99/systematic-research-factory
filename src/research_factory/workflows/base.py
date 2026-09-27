"""Step contract shared by the workflow engine and every step implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from ..domain.models import Finding
from ..domain.project_models import Experiment, ExperimentRecord, StepStatus, WorkflowRun

if TYPE_CHECKING:
    from ..services.container import Services


@dataclass
class StepContext:
    run: WorkflowRun
    record: ExperimentRecord
    services: Services
    artifacts: dict[str, str]  # step name -> artifact evidence ID, for completed prior steps
    attempt: int = 1

    @property
    def experiment(self) -> Experiment:
        return self.record.experiment

    def artifact(self, step: str) -> dict[str, Any]:
        doc: dict[str, Any] = self.services.evidence.load_json(self.artifacts[step])
        return doc


@dataclass
class StepOutcome:
    status: StepStatus
    artifact: dict[str, Any] | None = None
    findings: list[Finding] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)  # extra evidence the step read or wrote
    reason: str | None = None
    reason_code: str | None = None
    fail_run: bool = False  # the step completed, but its result means the run cannot continue
    run_decision: str | None = None  # final committee decision, when the step records one
    gate_context: str | None = None  # approval binds to this exact review context
    audit: dict[str, Any] = field(default_factory=dict)  # extra, non-sensitive audit fields


class Step(Protocol):
    name: str
    slug: str

    async def execute(self, ctx: StepContext) -> StepOutcome: ...
