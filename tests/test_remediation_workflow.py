"""Adversarial checkpoint, ownership, approval and replay regressions."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any

import anyio
import pytest
from sqlalchemy import insert

from research_factory.config import RetryPolicy, Settings, StatisticalThresholds
from research_factory.demo import replay_run
from research_factory.domain.clock import FixedClock
from research_factory.domain.errors import ConflictError, ForbiddenError
from research_factory.domain.project_models import ApprovalDecision, RunStatus, StepStatus
from research_factory.persistence import schema
from research_factory.persistence.blobs import FileBlobStore
from research_factory.services.container import Services, build_services
from research_factory.workflows.base import StepContext, StepOutcome
from research_factory.workflows.engine import WorkflowEngine
from research_factory.workflows.primary import primary_engine, primary_steps

from .conftest import make_experiment


def service(**kwargs: Any) -> Services:
    return build_services(
        Settings(
            database_url="sqlite://",
            blob_store="memory://",
            retry=RetryPolicy(base_delay_seconds=0),
            **kwargs,
        )
    )


@pytest.mark.anyio
@pytest.mark.parametrize("leaky", [False, True])
async def test_terminal_effect_survives_checkpoint_then_process_loss(
    monkeypatch: pytest.MonkeyPatch, leaky: bool
) -> None:
    s = service()
    record, _ = s.ledger.freeze(make_experiment(timing="period_end" if leaky else "acceptance"), "alice")
    engine = primary_engine(s)
    transition = engine._transition
    target = RunStatus.FAILED if leaky else RunStatus.COMPLETE
    crashed = False

    def crash_once(run: Any, status: RunStatus, actor: str, **kwargs: Any) -> Any:
        nonlocal crashed
        if status is target and not crashed:
            crashed = True
            raise ConnectionError("process loss after durable step checkpoint")
        return transition(run, status, actor, **kwargs)

    monkeypatch.setattr(engine, "_transition", crash_once)
    run = await engine.start(record.experiment_id, "alice")
    if not leaky:
        s.approvals.record(
            run_id=run.run_id,
            approver="bob",
            role="approver",
            decision=ApprovalDecision.APPROVE,
            reason="reviewed",
        )
        run = await engine.advance(run.run_id, "bob")
    assert crashed and run.status is RunStatus.NEEDS_REVIEW
    final = await engine.advance(run.run_id, "alice")
    assert final.status is target
    if leaky:
        assert s.repos.steps.get(run.run_id, "Statistical review") is None
    else:
        assert final.decision is ApprovalDecision.APPROVE


@pytest.mark.anyio
async def test_checkpoint_and_audit_rollback_together(monkeypatch: pytest.MonkeyPatch) -> None:
    s = service()
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    real = s.audit.append

    def fail(**kwargs: Any) -> Any:
        if kwargs["event_type"] == "step_completed":
            raise ConnectionError("audit unavailable")
        return real(**kwargs)

    monkeypatch.setattr(s.audit, "append", fail)
    run = await WorkflowEngine(s, primary_steps()[:1]).start(rec.experiment_id, "alice")
    assert run.status is RunStatus.NEEDS_REVIEW
    assert s.repos.steps.list(run.run_id) == []
    assert s.repos.findings.list_for_run(run.run_id) == []


@pytest.mark.anyio
async def test_takeover_fences_original_worker_before_publication() -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC), step=timedelta(0))
    s = build_services(
        Settings(database_url="sqlite://", blob_store="memory://", lease_seconds=1), clock=clock
    )

    class Takeover:
        name, slug = "Takeover", "takeover"

        async def execute(self, ctx: StepContext) -> StepOutcome:
            clock._current += timedelta(seconds=2)
            assert s.repos.runs.claim(
                ctx.run.run_id, "replacement", clock.now(), clock.now() + timedelta(seconds=10)
            )
            # Source evidence emitted inside execute must be fenced too, before
            # the final checkpoint wrapper is reached.
            s.evidence.record_json(
                {"stale": True},
                source_uri="test://stale",
                source_type="test",
                run_id=ctx.run.run_id,
                step=self.name,
            )
            return StepOutcome(StepStatus.COMPLETED, artifact={"stale_worker": True})

    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    engine = WorkflowEngine(s, [Takeover()])
    run = engine.create_run(rec.experiment_id, "alice")
    with pytest.raises(ConflictError, match="lease"):
        await engine.advance(run.run_id, "alice")
    assert s.repos.steps.list(run.run_id) == []
    assert s.repos.evidence.list_for_run(run.run_id) == []
    assert s.repos.runs.get(run.run_id).status is RunStatus.RUNNING  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_heartbeat_preserves_ownership_during_long_step(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC), step=timedelta(0))
    s = build_services(
        Settings(database_url="sqlite://", blob_store="memory://", lease_seconds=0.09), clock=clock
    )
    entered = anyio.Event()
    finish = anyio.Event()
    renewals = [anyio.Event(), anyio.Event()]
    renewed_at: list[datetime] = []
    renew = s.repos.runs.renew

    def observed_renewal(run_id: str, owner: str, expires_at: datetime) -> bool:
        renewed = renew(run_id, owner, expires_at)
        # Exclude the synchronous renewal before execute: this test must observe
        # the actual background heartbeat while the step is still suspended.
        if renewed and entered.is_set() and expires_at not in renewed_at and len(renewed_at) < len(renewals):
            renewed_at.append(expires_at)
            renewals[len(renewed_at) - 1].set()
        return renewed

    monkeypatch.setattr(s.repos.runs, "renew", observed_renewal)

    class Slow:
        name, slug = "Slow", "slow"

        async def execute(self, ctx: StepContext) -> StepOutcome:
            entered.set()
            await finish.wait()
            return StepOutcome(StepStatus.COMPLETED)

    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    engine = WorkflowEngine(s, [Slow()])
    run = engine.create_run(rec.experiment_id, "alice")
    with anyio.fail_after(10):
        async with anyio.create_task_group() as group:
            group.start_soon(engine.advance, run.run_id, "alice")
            await entered.wait()
            for renewal in renewals:
                clock._current += timedelta(seconds=0.06)
                await renewal.wait()
            # Logical time is now past the original 90ms lease, but the observed
            # heartbeat extended it. Host scheduling latency cannot expire it.
            assert renewed_at == [
                datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds) for seconds in (0.15, 0.21)
            ]
            with pytest.raises(ConflictError, match="another worker"):
                await engine.advance(run.run_id, "other")
            finish.set()
    assert s.repos.runs.get(run.run_id).status is RunStatus.COMPLETE  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_approval_is_invalidated_by_new_trials_and_can_be_recorded_again() -> None:
    s = service()
    record, _ = s.ledger.freeze(make_experiment(), "alice")
    engine = primary_engine(s)
    run = await engine.start(record.experiment_id, "alice")
    s.ledger.freeze(make_experiment(cost=6), "alice")
    with pytest.raises(ForbiddenError, match="cannot approve"):
        s.approvals.record(
            run_id=run.run_id,
            approver="bob",
            role="approver",
            decision=ApprovalDecision.APPROVE,
            reason="stale",
        )
    await engine.advance(run.run_id, "alice")
    first = s.approvals.record(
        run_id=run.run_id, approver="bob", role="approver", decision=ApprovalDecision.APPROVE, reason="fresh"
    )
    s.ledger.freeze(make_experiment(cost=7), "alice")
    run = await engine.advance(run.run_id, "alice")
    assert run.status is RunStatus.NEEDS_REVIEW and run.decision is None
    second = s.approvals.record(
        run_id=run.run_id,
        approver="bob",
        role="approver",
        decision=ApprovalDecision.APPROVE,
        reason="refreshed",
    )
    assert first.gate_context != second.gate_context
    assert (await engine.advance(run.run_id, "bob")).decision is ApprovalDecision.APPROVE


def test_identical_concurrent_blob_publications(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FileBlobStore(tmp_path)
    barrier = Barrier(8)
    link = os.link

    def publish(source: Any, destination: Any) -> None:
        barrier.wait(timeout=10)
        link(source, destination)

    monkeypatch.setattr(os, "link", publish)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            hashes = list(pool.map(store.put, [b"identical content"] * 8))
        assert len(set(hashes)) == 1
        assert store.get(hashes[0]) == b"identical content"
        assert not list(tmp_path.rglob("*.tmp"))
    finally:
        for path in tmp_path.rglob("*"):
            if path.is_file():
                path.chmod(0o600)


@pytest.mark.anyio
async def test_replay_uses_recorded_thresholds_and_never_calls_judgment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = service()
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    run = await primary_engine(s).start(rec.experiment_id, "alice")
    s.settings.thresholds = StatisticalThresholds(min_observations=999999)

    def forbidden(*args: Any) -> Any:
        raise AssertionError("exact replay may not call models or live data")

    monkeypatch.setattr(s.provider, "judge", forbidden)
    monkeypatch.setattr(s, "dataset", forbidden)
    replay = await replay_run(s, run.run_id)
    assert replay.identical and len(replay.compared) == 6
    assert "Economic rationale review" not in replay.compared
    assert s.pinned_snapshots == {}


@pytest.mark.anyio
async def test_replay_does_not_pin_another_run(monkeypatch: pytest.MonkeyPatch) -> None:
    s = service()
    early, _ = s.ledger.freeze(
        make_experiment(end=date(2021, 12, 30), as_of=datetime(2022, 1, 1, tzinfo=UTC)), "alice"
    )
    later, _ = s.ledger.freeze(make_experiment(), "alice")
    original = await WorkflowEngine(s, primary_steps()[:2]).start(early.experiment_id, "alice")
    start = WorkflowEngine.start
    observed: dict[str, Any] = {}

    async def overlap(
        self: WorkflowEngine, experiment_id: str, actor: str, project_type: str = "systematic_research"
    ) -> Any:
        if project_type == "replay":
            other = await start(WorkflowEngine(s, primary_steps()[:2]), later.experiment_id, "other")
            step = s.repos.steps.get(other.run_id, "Data acquisition")
            assert step and step.artifact_evidence_id
            observed.update(s.evidence.load_json(step.artifact_evidence_id))
        return await start(self, experiment_id, actor, project_type)

    monkeypatch.setattr(WorkflowEngine, "start", overlap)
    assert (await replay_run(s, original.run_id)).identical
    assert observed["last_session"] == "2023-12-29"


def test_audit_events_include_entries_after_page_limit() -> None:
    s = service()
    with s.engine.begin() as conn:
        conn.execute(
            insert(schema.audit_events),
            [
                dict(
                    run_id="run-long",
                    step="test",
                    actor="test",
                    event_type="probe",
                    payload={},
                    payload_hash="0" * 64,
                    created_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
                for _ in range(10003)
            ],
        )
    events = s.audit.events("run-long")
    assert len(events) == 10003
    assert events[-1].event_id == 10003


def test_concurrent_evidence_and_trial_results_are_idempotent(tmp_path: Path) -> None:
    s = build_services(
        Settings(database_url=f"sqlite:///{tmp_path / 'concurrent.db'}", blob_store="memory://")
    )
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    barrier = Barrier(8)

    def persist(_: int) -> str:
        barrier.wait(timeout=10)
        ref = s.evidence.record_json({"identical": True}, source_uri="test://same", source_type="test")
        s.ledger.record_result(rec.experiment_id, 0.25, 123)
        return ref.evidence_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert len(set(pool.map(persist, range(8)))) == 1
    assert s.ledger.get(rec.experiment_id).sharpe_per_period == 0.25
    s.engine.dispose()


@pytest.mark.anyio
async def test_request_cancellation_leaves_an_explicit_resumable_pause() -> None:
    s = service()
    entered = anyio.Event()

    class AwaitCancellation:
        name, slug = "Wait", "wait"

        async def execute(self, ctx: StepContext) -> StepOutcome:
            entered.set()
            await anyio.sleep_forever()
            return StepOutcome(StepStatus.COMPLETED)

    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    engine = WorkflowEngine(s, [AwaitCancellation()])
    run = engine.create_run(rec.experiment_id, "alice")
    async with anyio.create_task_group() as group:
        group.start_soon(engine.advance, run.run_id, "alice")
        await entered.wait()
        group.cancel_scope.cancel()
    stopped = engine.get_run(run.run_id)
    assert stopped.status is RunStatus.NEEDS_REVIEW
    assert (stopped.status_reason or "").startswith("CANCELLED")


def test_freeze_and_create_run_cannot_commit_without_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    s = service()
    experiment = make_experiment()
    real = s.audit.append

    def unavailable(**kwargs: Any) -> Any:
        raise ConnectionError("audit storage unavailable")

    monkeypatch.setattr(s.audit, "append", unavailable)
    with pytest.raises(ConnectionError):
        s.ledger.freeze(experiment, "alice")
    assert s.repos.experiments.get(experiment.experiment_id) is None
    assert s.repos.experiments.count_in_family(experiment.hypothesis.research_family) == 0
    monkeypatch.setattr(s.audit, "append", real)
    rec, _ = s.ledger.freeze(experiment, "alice")
    assert rec.trial_number == 1
    monkeypatch.setattr(s.audit, "append", unavailable)
    with pytest.raises(ConnectionError):
        primary_engine(s).create_run(rec.experiment_id, "alice")
    assert s.repos.runs.list() == []
