"""Service wiring. One place builds every dependency, so tests can swap any of them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine

from ..config import Settings
from ..data.registry import get_dataset
from ..data.world import MarketDataset
from ..domain.clock import Clock, SystemClock
from ..judgment.providers import JudgmentProvider, provider_from_settings
from ..persistence.blobs import BlobStore, blob_store_from_url
from ..persistence.db import make_engine, upgrade
from ..persistence.repositories import Repositories
from ..workflows.faults import FaultInjector
from .approvals import ApprovalService
from .audit import AuditLog
from .budget import BudgetGuard
from .evidence import EvidenceStore
from .ledger import ResearchLedger


@dataclass
class Services:
    settings: Settings
    clock: Clock
    engine: Engine
    repos: Repositories
    blobs: BlobStore
    evidence: EvidenceStore
    audit: AuditLog
    ledger: ResearchLedger
    approvals: ApprovalService
    budget: BudgetGuard
    provider: JudgmentProvider
    faults: FaultInjector
    pinned_snapshots: dict[str, str] = field(default_factory=dict)  # dataset name -> snapshot evidence ID
    _snapshots: dict[str, MarketDataset] = field(default_factory=dict)

    def dataset(self, name: str) -> MarketDataset:
        """The live source dataset (a fault-injection point)."""
        self.faults.check("data_source")
        return get_dataset(name)

    def snapshot(self, evidence_id: str) -> MarketDataset:
        """A dataset snapshot loaded from evidence. Replays read evidence, never live data."""
        if evidence_id not in self._snapshots:
            self._snapshots[evidence_id] = MarketDataset.from_bytes(self.evidence.load_bytes(evidence_id))
        return self._snapshots[evidence_id]


def build_services(
    settings: Settings | None = None,
    *,
    engine: Engine | None = None,
    blobs: BlobStore | None = None,
    clock: Clock | None = None,
    provider: JudgmentProvider | None = None,
    faults: FaultInjector | None = None,
    migrate: bool = True,
) -> Services:
    settings = settings or Settings()
    clock = clock or SystemClock()
    engine = engine or make_engine(settings.database_url)
    if migrate:
        upgrade(engine)
    repos = Repositories(engine)
    if blobs is None:
        s3: dict[str, Any] = {}
        if settings.blob_store.startswith("s3://"):
            s3 = {
                "endpoint_url": settings.s3_endpoint_url,
                "key_id": settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None,
                "secret": settings.s3_secret_access_key.get_secret_value()
                if settings.s3_secret_access_key
                else None,
            }
        blobs = blob_store_from_url(settings.blob_store, **s3)
    audit = AuditLog(repos.audit, clock)
    if provider is None:
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        provider = provider_from_settings(
            settings.model_provider, settings.anthropic_model, key, settings.retry.timeout_seconds
        )
    return Services(
        settings=settings,
        clock=clock,
        engine=engine,
        repos=repos,
        blobs=blobs,
        evidence=EvidenceStore(repos.evidence, blobs, clock),
        audit=audit,
        ledger=ResearchLedger(
            repos.experiments, audit, clock, transaction=lambda: repos.transaction(guard_ledger=True)
        ),
        approvals=ApprovalService(repos, audit, clock),
        budget=BudgetGuard(settings.budgets, repos.usage, repos.runs, clock),
        provider=provider,
        faults=faults or FaultInjector(),
    )
