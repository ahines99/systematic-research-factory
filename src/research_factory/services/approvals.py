"""Committee gate and human approvals (RSF-042, RSF-063).

The gate is deterministic and computed from findings:

* any blocking finding                 -> reject
* any failed statistical threshold     -> reject
* any NEEDS_EVIDENCE finding            -> needs_more_evidence
* any other high-severity finding       -> needs_more_evidence
* otherwise                             -> approve

A human approver records the decision. Policies, enforced here and not in prompts:
the approver must hold the approver role, must not be the run's requester, and may
record "approve" only when the gate recommends approval. Rejecting or asking for more
evidence is always allowed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ..domain.clock import Clock
from ..domain.errors import ConflictError, ForbiddenError, NotFoundError
from ..domain.models import Finding, Severity
from ..domain.project_models import ApprovalDecision, ApprovalRecord, RunStatus
from ..persistence.repositories import Repositories
from .audit import AuditLog

COMMITTEE_STEP = "Research committee"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


@dataclass(frozen=True)
class Gate:
    recommendation: ApprovalDecision
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"recommendation": str(self.recommendation), "reasons": self.reasons}


def compute_gate(findings: list[Finding]) -> Gate:
    blocking = [f for f in findings if f.severity is Severity.BLOCKING]
    if blocking:
        return Gate(ApprovalDecision.REJECT, [f"Blocking finding: {f.title}." for f in blocking])
    thresholds = [f for f in findings if f.finding_type == "statistical_threshold"]
    if thresholds:
        return Gate(
            ApprovalDecision.REJECT, [f"Statistical threshold failed: {f.title}." for f in thresholds]
        )
    needs = [f for f in findings if f.finding_type == "needs_evidence"]
    if needs:
        return Gate(ApprovalDecision.NEEDS_MORE_EVIDENCE, [f"Evidence needed: {f.title}." for f in needs])
    high = [f for f in findings if f.severity is Severity.HIGH]
    if high:
        return Gate(
            ApprovalDecision.NEEDS_MORE_EVIDENCE, [f"High-severity finding: {f.title}." for f in high]
        )
    return Gate(ApprovalDecision.APPROVE, ["No blocking, statistical or evidence findings."])


class ApprovalService:
    def __init__(self, repos: Repositories, audit: AuditLog, clock: Clock):
        self.repos = repos
        self.audit = audit
        self.clock = clock

    def pending_gate(self, run_id: str) -> Gate:
        return compute_gate(self.repos.findings.list_for_run(run_id))

    def record(
        self, *, run_id: str, approver: str, role: str, decision: ApprovalDecision, reason: str
    ) -> ApprovalRecord:
        run = self.repos.runs.get(run_id)
        if run is None:
            raise NotFoundError(f"run {run_id} not found")
        if role != "approver":
            raise ForbiddenError("only the approver role can record committee decisions")
        if approver == run.requested_by:
            raise ForbiddenError("the approver cannot be the person who requested the run")
        if (
            run.status is not RunStatus.NEEDS_REVIEW
            or run.current_step != COMMITTEE_STEP
            or not (run.status_reason or "").startswith(APPROVAL_REQUIRED)
        ):
            raise ConflictError("this run is not awaiting a committee decision")
        gate = self.pending_gate(run_id)
        if decision is ApprovalDecision.APPROVE and gate.recommendation is not ApprovalDecision.APPROVE:
            raise ForbiddenError(
                f"cannot approve: the gate recommends {gate.recommendation} ({' '.join(gate.reasons)})",
                details={"gate": gate.to_dict()},
            )
        record = ApprovalRecord(
            approval_id=f"apr_{uuid.uuid4().hex[:20]}",
            run_id=run_id,
            step=COMMITTEE_STEP,
            approver=approver,
            decision=decision,
            reason=reason,
            created_at=self.clock.now(),
        )
        self.repos.approvals.add(record)
        self.audit.append(
            run_id=run_id,
            step=COMMITTEE_STEP,
            event_type="approval_recorded",
            actor=approver,
            payload={"approval_id": record.approval_id, "decision": str(decision), "gate": gate.to_dict()},
        )
        return record
