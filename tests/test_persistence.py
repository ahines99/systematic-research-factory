"""RSF-011 to RSF-015 (and RSF-060): schema, repositories, evidence, audit, ledger.

The repository contract tests run against SQLite by default and also against PostgreSQL
when ``DATABASE_URL`` points at one (CI does this).
"""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from research_factory.domain.errors import ConflictError, NotFoundError
from research_factory.domain.identity import sha256_hex
from research_factory.domain.models import AuditEvent, Confidence, EvidenceRef, Finding, Severity
from research_factory.domain.project_models import (
    ApprovalDecision,
    ApprovalRecord,
    RunStatus,
    StepResult,
    StepStatus,
    WorkflowRun,
)
from research_factory.persistence.blobs import FileBlobStore, MemoryBlobStore, S3BlobStore
from research_factory.persistence.db import downgrade, make_engine, upgrade
from research_factory.persistence.repositories import Repositories
from research_factory.persistence.schema import metadata
from research_factory.services.audit import redact

from .conftest import make_experiment

NOW = datetime(2024, 1, 2, tzinfo=UTC)
URLS = ["sqlite://"] + (
    [os.environ["DATABASE_URL"]] if os.environ.get("DATABASE_URL", "").startswith("postgresql") else []
)


@pytest.fixture(params=URLS, ids=lambda u: u.split(":")[0])
def engine(request: pytest.FixtureRequest) -> Engine:
    eng = make_engine(request.param)
    if eng.dialect.name == "postgresql":
        downgrade(eng)
    upgrade(eng)
    return eng


@pytest.fixture
def repos(engine: Engine) -> Repositories:
    return Repositories(engine)


def test_migrations_match_declared_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), metadata) == []


def test_downgrade_and_upgrade_round_trip() -> None:
    eng = make_engine("sqlite://")
    upgrade(eng)
    downgrade(eng)
    upgrade(eng)


@pytest.mark.parametrize("table", ["audit_events", "experiments", "evidence", "approvals", "trial_results"])
def test_append_only_tables_reject_update_and_delete(repos: Repositories, engine: Engine, table: str) -> None:
    _seed(repos)
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))
    first_column = {
        "audit_events": "step",
        "experiments": "created_by",
        "evidence": "source_uri",
        "approvals": "reason",
        "trial_results": "n_obs",
    }[table]
    value = "0" if table == "trial_results" else "'tampered'"
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text(f"UPDATE {table} SET {first_column} = {value}"))


def test_truncate_is_blocked_on_postgres(repos: Repositories, engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("TRUNCATE triggers are PostgreSQL-specific; SQLite has no TRUNCATE")
    _seed(repos)
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("TRUNCATE audit_events CASCADE"))


def _seed(repos: Repositories) -> WorkflowRun:
    from research_factory.domain.project_models import ExperimentRecord

    exp = make_experiment()
    repos.experiments.add(
        ExperimentRecord(
            experiment_id=exp.experiment_id,
            research_family="f",
            trial_number=1,
            experiment=exp,
            created_by="alice",
            created_at=NOW,
        )
    )
    repos.experiments.record_result(exp.experiment_id, 0.1, 100, NOW)
    run = WorkflowRun(
        run_id="run_1",
        experiment_id=exp.experiment_id,
        status=RunStatus.PENDING,
        requested_by="alice",
        created_at=NOW,
        updated_at=NOW,
    )
    repos.runs.add(run)
    ref = EvidenceRef(
        evidence_id="ev_1", source_uri="rsf://x", source_type="t", content_hash="a" * 64, retrieved_at=NOW
    )
    repos.evidence.add(ref)
    repos.evidence.link("run_1", "ev_1", "s")
    repos.audit.append(
        AuditEvent(
            run_id="run_1",
            step="s",
            event_type="e",
            actor="a",
            created_at=NOW,
            payload={"k": 1},
            payload_hash="h",
        )
    )
    repos.approvals.add(
        ApprovalRecord(
            approval_id="apr_1",
            run_id="run_1",
            step="s",
            approver="bob",
            decision=ApprovalDecision.REJECT,
            reason="no good",
            created_at=NOW,
        )
    )
    return run


def test_run_repository_compare_and_set(repos: Repositories) -> None:
    run = _seed(repos)
    running = run.model_copy(update={"status": RunStatus.RUNNING, "updated_at": NOW + timedelta(seconds=1)})
    repos.runs.update(running, expected_status=RunStatus.PENDING)
    with pytest.raises(ConflictError):
        repos.runs.update(running, expected_status=RunStatus.PENDING)
    assert repos.runs.get("run_1").status is RunStatus.RUNNING  # type: ignore[union-attr]
    assert repos.runs.count_created_since("alice", NOW - timedelta(days=1)) == 1


def test_completed_step_results_are_immutable(repos: Repositories) -> None:
    _seed(repos)
    base = StepResult(
        run_id="run_1", step="Backtest", status=StepStatus.NEEDS_REVIEW, idempotency_key="k", created_at=NOW
    )
    repos.steps.save(base)
    repos.steps.save(base.model_copy(update={"status": StepStatus.COMPLETED, "attempts": 2}))
    assert repos.steps.get("run_1", "Backtest").attempts == 2  # type: ignore[union-attr]
    with pytest.raises(ConflictError):
        repos.steps.save(base)


def test_findings_round_trip_with_evidence(repos: Repositories) -> None:
    _seed(repos)
    f = Finding(
        finding_id="fnd_1",
        step="s",
        finding_type="t",
        title="T",
        statement="S",
        severity=Severity.HIGH,
        confidence=Confidence.LOW,
        evidence_ids=("ev_1",),
        assumptions=("a",),
        metadata={"x": 1},
    )
    repos.findings.add("run_1", f, NOW)
    repos.findings.add("run_1", f, NOW)  # idempotent
    assert repos.findings.list_for_run("run_1") == [f]


def test_evidence_is_idempotent_and_detects_collisions(repos: Repositories) -> None:
    _seed(repos)
    ref = repos.evidence.get("ev_1")
    assert ref is not None
    repos.evidence.add(ref)
    with pytest.raises(ConflictError):
        repos.evidence.add(ref.model_copy(update={"content_hash": "b" * 64}))
    assert [e.evidence_id for _, e in repos.evidence.list_for_run("run_1")] == ["ev_1"]


def test_trial_results_are_write_once(repos: Repositories) -> None:
    run = _seed(repos)
    repos.experiments.record_result(run.experiment_id, 0.1, 100, NOW)  # same value: no-op
    with pytest.raises(ConflictError):
        repos.experiments.record_result(run.experiment_id, 0.2, 100, NOW)


def test_api_keys_and_usage(repos: Repositories) -> None:
    repos.api_keys.add("k1", "h" * 64, "alice", "researcher", NOW)
    assert repos.api_keys.find_by_hash("h" * 64)["owner"] == "alice"  # type: ignore[index]
    repos.api_keys.revoke("k1", NOW)
    with pytest.raises(NotFoundError):
        repos.api_keys.revoke("k1", NOW)
    repos.usage.add(
        run_id="r", step="s", model="m", input_tokens=10, output_tokens=5, cost_usd=0.5, created_at=NOW
    )
    assert repos.usage.totals_for_run("r") == (15, 0.5)
    assert repos.usage.cost_since(NOW - timedelta(hours=1)) == 0.5


# ----------------------------------------------------------------------- blobs


def test_memory_blob_store() -> None:
    store = MemoryBlobStore()
    blob = store.put(b"hello")
    assert blob == sha256_hex(b"hello") and store.get(blob) == b"hello" and store.put(b"hello") == blob
    with pytest.raises(NotFoundError):
        store.get("0" * 64)


def test_file_blob_store_is_write_once_and_verified(tmp_path: Path) -> None:
    store = FileBlobStore(tmp_path)
    blob = store.put(b"data")
    path = store._path(blob)
    assert not os.access(path, os.W_OK)
    path.chmod(stat.S_IWRITE | stat.S_IREAD)
    path.write_bytes(b"tampered")
    with pytest.raises(ConflictError, match="integrity"):
        store.get(blob)
    with pytest.raises(NotFoundError):
        store.get("../../etc/passwd")


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict] = []

    def head_object(self, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise _ClientError("404")
        return {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, IfNoneMatch: str) -> None:
        self.puts.append({"Key": Key, "IfNoneMatch": IfNoneMatch})
        if Key in self.objects:
            raise _ClientError("PreconditionFailed")
        self.objects[Key] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        import io

        return {"Body": io.BytesIO(self.objects[Key])}


class _ClientError(Exception):
    def __init__(self, code: str):
        self.response = {"Error": {"Code": code}}


def test_s3_blob_store_uses_conditional_writes() -> None:
    client = FakeS3()
    store = S3BlobStore("bucket", client)
    blob = store.put(b"x")
    assert store.put(b"x") == blob and len(client.puts) == 1
    assert client.puts[0]["IfNoneMatch"] == "*"
    assert store.get(blob) == b"x" and store.exists(blob)
    with pytest.raises(NotFoundError):
        store.get("1" * 64)


# ----------------------------------------------------------------------- services


def test_evidence_store_dedupes_and_links(services) -> None:
    a = services.evidence.record_json({"x": 1}, source_uri="rsf://t", source_type="t")
    b = services.evidence.record_json({"x": 1}, source_uri="rsf://t", source_type="t")
    c = services.evidence.record_json({"x": 2}, source_uri="rsf://t", source_type="t")
    assert a.evidence_id == b.evidence_id != c.evidence_id
    assert services.evidence.load_json(a.evidence_id) == {"x": 1}
    derived = services.evidence.record_derived(a, b"text", kind="text")
    assert derived.metadata["derived_from"] == a.evidence_id


def test_audit_payloads_are_redacted_and_hashed(services) -> None:
    event = services.audit.append(
        run_id=None,
        step="s",
        event_type="e",
        actor="a",
        payload={
            "api_key": "sk-secret",
            "nested": {"Authorization": "Bearer x"},
            "input_tokens": 5,
            "big": "x" * 5000,
        },
    )
    assert event.payload["api_key"] == "[REDACTED]"
    assert event.payload["nested"]["Authorization"] == "[REDACTED]"
    assert event.payload["input_tokens"] == 5
    assert event.payload["big"]["length"] == 5000
    assert len(event.payload_hash) == 64 and event.event_id is not None
    assert redact([{"password": "p"}]) == [{"password": "[REDACTED]"}]


def test_audit_repository_has_no_mutation_methods(services) -> None:
    public = {n for n in dir(services.repos.audit) if not n.startswith("_")}
    assert public == {"append", "list", "engine"}


def test_trial_context_is_deterministic(services, clock) -> None:
    rec1, _ = services.ledger.freeze(make_experiment(cost=1), "a")
    services.ledger.record_result(rec1.experiment_id, 0.05, 100)
    rec2, _ = services.ledger.freeze(make_experiment(cost=2), "a")
    before = services.ledger.trial_context(rec2.experiment_id)
    rec3, _ = services.ledger.freeze(make_experiment(cost=3), "a")
    services.ledger.record_result(rec3.experiment_id, 0.07, 100)
    assert services.ledger.trial_context(rec2.experiment_id) == before == (2, [0.05])
