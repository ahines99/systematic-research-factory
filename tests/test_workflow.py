"""RSF-022, RSF-023, RSF-038 to RSF-047: workflow engine, approvals, recovery, judgment."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from pathlib import Path

import anyio
import pytest

from research_factory.config import Budgets, RetryPolicy, Settings
from research_factory.domain.errors import ConflictError, ForbiddenError
from research_factory.domain.project_models import ApprovalDecision, RunStatus, StepStatus
from research_factory.judgment.providers import RulesProvider, ScriptedProvider
from research_factory.services.container import Services, build_services
from research_factory.workflows.base import StepContext, StepOutcome
from research_factory.workflows.engine import WorkflowEngine
from research_factory.workflows.faults import FaultInjector, FaultKind, FaultRule
from research_factory.workflows.primary import PROJECT_STEPS, primary_engine

from .conftest import make_experiment

pytestmark = pytest.mark.anyio

FAST_RETRY = RetryPolicy(max_attempts=3, base_delay_seconds=0.0, max_delay_seconds=0.0, timeout_seconds=60)


def _services(clock, **kw) -> Services:  # type: ignore[no-untyped-def]
    settings = kw.pop("settings", None) or Settings(
        database_url="sqlite://", blob_store="memory://", retry=FAST_RETRY
    )
    return build_services(settings, clock=clock, **kw)


async def _start(services: Services, **exp_kw) -> tuple[WorkflowEngine, str]:  # type: ignore[no-untyped-def]
    rec, _ = services.ledger.freeze(make_experiment(**exp_kw), "alice")
    engine = primary_engine(services)
    run = await engine.start(rec.experiment_id, "alice")
    return engine, run.run_id


def _events(services: Services, run_id: str, event_type: str) -> list:  # type: ignore[type-arg]
    return [e for e in services.audit.events(run_id) if e.event_type == event_type]


async def test_clean_run_pauses_for_committee_then_completes(clock) -> None:
    s = _services(clock)
    engine, run_id = await _start(s)
    run = engine.get_run(run_id)
    assert run.status is RunStatus.NEEDS_REVIEW and run.current_step == "Research committee"
    assert run.status_reason.startswith("APPROVAL_REQUIRED")  # type: ignore[union-attr]
    assert [r.step for r in s.repos.steps.list(run_id) if r.status is StepStatus.COMPLETED] == PROJECT_STEPS[
        :-1
    ]

    s.approvals.record(
        run_id=run_id, approver="bob", role="approver", decision=ApprovalDecision.APPROVE, reason="Clean."
    )
    run = await engine.advance(run_id, "bob")
    assert run.status is RunStatus.COMPLETE and run.decision is ApprovalDecision.APPROVE
    # Completed steps were reused, not executed again.
    assert len(_events(s, run_id, "step_reused")) == 8
    started = [e.step for e in _events(s, run_id, "step_started")]
    assert started.count("Backtest") == 1 and started.count("Research committee") == 2


async def test_every_step_writes_artifact_and_audit(clock) -> None:
    s = _services(clock)
    _, run_id = await _start(s)
    for result in s.repos.steps.list(run_id):
        assert result.artifact_evidence_id and s.evidence.exists(result.artifact_evidence_id)
    types = {e.event_type for e in s.audit.events(run_id)}
    assert {
        "run_created",
        "run_status_changed",
        "step_started",
        "step_completed",
        "step_needs_review",
    } <= types


async def test_approval_policies_are_enforced_server_side(clock) -> None:
    s = _services(clock)
    engine, run_id = await _start(s, dataset="synthetic:v1:null")  # gate says reject
    with pytest.raises(ForbiddenError, match="role"):
        s.approvals.record(
            run_id=run_id, approver="bob", role="researcher", decision=ApprovalDecision.REJECT, reason="x" * 5
        )
    with pytest.raises(ForbiddenError, match="requested the run"):
        s.approvals.record(
            run_id=run_id, approver="alice", role="approver", decision=ApprovalDecision.REJECT, reason="x" * 5
        )
    with pytest.raises(ForbiddenError, match="cannot approve"):
        s.approvals.record(
            run_id=run_id, approver="bob", role="approver", decision=ApprovalDecision.APPROVE, reason="x" * 5
        )
    s.approvals.record(
        run_id=run_id, approver="bob", role="approver", decision=ApprovalDecision.REJECT, reason="Noise."
    )
    run = await engine.advance(run_id, "bob")
    assert run.status is RunStatus.COMPLETE and run.decision is ApprovalDecision.REJECT
    with pytest.raises(ConflictError):
        s.approvals.record(
            run_id=run_id, approver="bob", role="approver", decision=ApprovalDecision.REJECT, reason="again"
        )


async def test_leak_fails_the_run_at_the_audit(clock) -> None:
    s = _services(clock)
    engine, run_id = await _start(s, timing="period_end")
    run = engine.get_run(run_id)
    assert run.status is RunStatus.FAILED and run.current_step == "Leakage audit"
    assert "knowledge_time" in (run.status_reason or "")
    assert s.repos.steps.get(run_id, "Statistical review") is None
    assert await engine.advance(run_id, "alice") == run  # terminal runs stay terminal


async def test_resume_after_process_restart(clock, tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'rsf.db'}",
        blob_store=f"file://{tmp_path / 'blobs'}",
        retry=FAST_RETRY,
    )
    first = build_services(settings, clock=clock)
    _, run_id = await _start(first)
    first.engine.dispose()

    second = build_services(settings, clock=clock)  # a new process: fresh caches, same storage
    second.approvals.record(
        run_id=run_id, approver="bob", role="approver", decision=ApprovalDecision.APPROVE, reason="ok!"
    )
    run = await primary_engine(second).advance(run_id, "bob")
    assert run.status is RunStatus.COMPLETE
    assert len(_events(second, run_id, "step_reused")) == 8


async def test_reruns_of_an_experiment_are_byte_identical(clock) -> None:
    s = _services(clock)
    _, run_a = await _start(s)
    _, run_b = await _start(s)
    a = {r.step: r.artifact_evidence_id for r in s.repos.steps.list(run_a)}
    b = {r.step: r.artifact_evidence_id for r in s.repos.steps.list(run_b)}
    for step in PROJECT_STEPS[:6]:  # deterministic steps
        assert s.evidence.get(a[step]).content_hash == s.evidence.get(b[step]).content_hash


async def test_transient_timeout_is_retried(clock) -> None:
    s = _services(clock, faults=FaultInjector([FaultRule("data_source", FaultKind.TIMEOUT, times=1)]))
    engine, run_id = await _start(s)
    assert engine.get_run(run_id).status is RunStatus.NEEDS_REVIEW  # reached the committee
    retries = _events(s, run_id, "step_retry")
    assert len(retries) == 1 and retries[0].payload["code"] == "TIMEOUT"
    assert s.repos.steps.get(run_id, "Data acquisition").attempts == 2  # type: ignore[union-attr]


async def test_persistent_outage_pauses_and_recovers(clock) -> None:
    faults = FaultInjector([FaultRule("data_source", FaultKind.OUTAGE, times=3)])
    s = _services(clock, faults=faults)
    engine, run_id = await _start(s)
    run = engine.get_run(run_id)
    assert run.status is RunStatus.NEEDS_REVIEW and run.status_reason.startswith("UPSTREAM_UNAVAILABLE")  # type: ignore[union-attr]
    run = await engine.advance(run_id, "alice")  # the source is back
    assert run.current_step == "Research committee"


async def test_malformed_data_needs_evidence(clock) -> None:
    s = _services(clock, faults=FaultInjector([FaultRule("data_source", FaultKind.MALFORMED)]))
    engine, run_id = await _start(s)
    run = engine.get_run(run_id)
    assert run.status is RunStatus.NEEDS_REVIEW and run.status_reason.startswith("NEEDS_EVIDENCE")  # type: ignore[union-attr]
    assert any(f.finding_type == "needs_evidence" for f in s.repos.findings.list_for_run(run_id))


async def test_budget_exhaustion_pauses_the_run(clock) -> None:
    settings = Settings(
        database_url="sqlite://",
        blob_store="memory://",
        retry=FAST_RETRY,
        budgets=Budgets(max_tokens_per_run=500),
    )

    class Costly(RulesProvider):
        def judge(self, request):  # type: ignore[no-untyped-def]
            return replace(super().judge(request), input_tokens=1000, output_tokens=200)

    s = _services(clock, settings=settings, provider=Costly())
    engine, run_id = await _start(s)
    run = engine.get_run(run_id)
    assert run.status is RunStatus.NEEDS_REVIEW and run.status_reason.startswith("BUDGET_EXCEEDED")  # type: ignore[union-attr]
    assert run.current_step == "Implementation review"  # first model call used 1200 tokens


async def test_daily_cap_blocks_model_calls(clock) -> None:
    settings = Settings(
        database_url="sqlite://",
        blob_store="memory://",
        retry=FAST_RETRY,
        budgets=Budgets(max_cost_usd_per_day=1.0),
    )
    s = _services(clock, settings=settings)
    s.budget.record(run_id=None, step="x", model="m", input_tokens=1, output_tokens=1, cost_usd=5.0)
    engine, run_id = await _start(s)
    assert "daily model-spend cap" in (engine.get_run(run_id).status_reason or "")


async def test_uncited_or_invented_evidence_is_rejected(clock) -> None:
    bad = {
        "verdict": "supported",
        "confidence": "high",
        "summary": "Looks great to me overall.",
        "claims": [
            {"kind": "fact", "statement": "Sharpe is 9.", "evidence_ids": ["ev_invented"]},
            {"kind": "calculation", "statement": "IC is 0.5 exactly.", "evidence_ids": []},
        ],
        "open_questions": [],
        "needs_evidence": False,
    }
    provider = ScriptedProvider(outputs=deque([bad, bad]))
    s = _services(clock, provider=provider)
    engine, run_id = await _start(s)
    run = engine.get_run(run_id)
    assert run.current_step == "Economic rationale review" and run.status is RunStatus.NEEDS_REVIEW
    finding = next(f for f in s.repos.findings.list_for_run(run_id) if f.title == "Reviewer output rejected")
    assert "does not exist in this run" in finding.statement and "without evidence" in finding.statement
    assert provider.requests[1].feedback  # the retry told the reviewer what was wrong


async def test_reviewer_can_recover_after_feedback(clock) -> None:
    bad = {
        "verdict": "maybe",
        "confidence": "high",
        "summary": "Not a valid verdict here.",
        "claims": [{"kind": "assumption", "statement": "Something.", "evidence_ids": []}],
        "open_questions": [],
        "needs_evidence": False,
    }
    s = _services(clock, provider=ScriptedProvider(outputs=deque([bad])))  # then falls back to rules
    engine, run_id = await _start(s)
    assert engine.get_run(run_id).current_step == "Research committee"


async def test_judgment_audit_events_are_version_stamped(clock) -> None:
    s = _services(clock)
    _, run_id = await _start(s)
    event = next(e for e in _events(s, run_id, "step_completed") if e.step == "Economic rationale review")
    for key in ("model", "prompt_version", "skill_version", "schema_version", "input_tokens", "cost_usd"):
        assert key in event.payload
    assert event.payload["skill_version"] != "none"


async def test_unexpected_crash_fails_closed(clock) -> None:
    class Boom:
        name, slug = "Boom", "boom"

        async def execute(self, ctx: StepContext) -> StepOutcome:
            raise RuntimeError("secret internal detail")

    s = _services(clock)
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    run = await WorkflowEngine(s, [Boom()]).start(rec.experiment_id, "alice")
    assert run.status is RunStatus.FAILED and run.status_reason == "internal error"
    assert "secret" not in str([e.payload for e in s.audit.events(run.run_id)])


async def test_invalid_transitions_are_rejected(clock) -> None:
    s = _services(clock)
    engine, run_id = await _start(s, timing="period_end")
    run = engine.get_run(run_id)
    with pytest.raises(ConflictError, match="invalid transition"):
        engine._transition(run, RunStatus.RUNNING, "x")


async def test_step_timeout_is_enforced(clock) -> None:
    class Slow:
        name, slug = "Slow", "slow"

        async def execute(self, ctx: StepContext) -> StepOutcome:
            await anyio.sleep(5)
            return StepOutcome(StepStatus.COMPLETED)

    settings = Settings(
        database_url="sqlite://",
        blob_store="memory://",
        retry=RetryPolicy(max_attempts=2, base_delay_seconds=0, timeout_seconds=0.05),
    )
    s = _services(clock, settings=settings)
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    run = await WorkflowEngine(s, [Slow()]).start(rec.experiment_id, "alice")
    assert run.status is RunStatus.NEEDS_REVIEW and run.status_reason.startswith("TIMEOUT")  # type: ignore[union-attr]
    assert len(_events(s, run.run_id, "step_retry")) == 1
