"""RSF-060, RSF-076: the full workflow on PostgreSQL, including concurrent runs.

Runs only when ``DATABASE_URL`` points at PostgreSQL (the CI ``postgres`` job).
"""

from __future__ import annotations

import os

import anyio
import pytest

from research_factory.config import Settings
from research_factory.domain.project_models import ApprovalDecision, RunStatus
from research_factory.persistence.db import downgrade, make_engine
from research_factory.services.container import build_services
from research_factory.workflows.primary import primary_engine

from .conftest import make_experiment

URL = os.environ.get("DATABASE_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not URL.startswith("postgresql"), reason="needs DATABASE_URL pointing at PostgreSQL"),
]


def _services():  # type: ignore[no-untyped-def]
    engine = make_engine(URL)
    downgrade(engine)
    return build_services(Settings(database_url=URL, blob_store="memory://"), engine=engine)


def test_full_workflow_on_postgres() -> None:
    services = _services()
    record, _ = services.ledger.freeze(make_experiment(), "alice")
    engine = primary_engine(services)
    run = anyio.run(engine.start, record.experiment_id, "alice")
    assert run.status is RunStatus.NEEDS_REVIEW
    services.approvals.record(
        run_id=run.run_id, approver="bob", role="approver", decision=ApprovalDecision.APPROVE, reason="clean"
    )
    assert anyio.run(engine.advance, run.run_id, "bob").status is RunStatus.COMPLETE


def test_concurrent_runs_do_not_interfere() -> None:
    services = _services()
    experiments = [make_experiment(cost=float(c)) for c in (3, 4, 5, 6)]
    ids = [services.ledger.freeze(e, "alice")[0].experiment_id for e in experiments]

    async def run_all() -> list:  # type: ignore[type-arg]
        results: list = []  # type: ignore[type-arg]
        async with anyio.create_task_group() as tg:
            for experiment_id in ids:

                async def one(eid: str = experiment_id) -> None:
                    results.append(await primary_engine(services).start(eid, "alice"))

                tg.start_soon(one)
        return results

    runs = anyio.run(run_all)
    assert len({r.run_id for r in runs}) == 4
    for run in runs:
        steps = services.repos.steps.list(run.run_id)
        assert all(s.run_id == run.run_id for s in steps) and len(steps) == 9
    assert sorted(r.trial_number for r in services.repos.experiments.list_family("earnings-drift")) == [
        1,
        2,
        3,
        4,
    ]
