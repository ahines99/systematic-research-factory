"""Operator recovery paths added by the audit remediation."""

from __future__ import annotations

import threading
import time
from typing import Any

import anyio
import pytest

from research_factory import cli
from research_factory.persistence.budget import BudgetReservations
from research_factory.report import render_html
from research_factory.services.budget import start_of_day
from research_factory.services.container import Services
from research_factory.workflows import steps
from research_factory.workflows.base import StepContext
from research_factory.workflows.engine import WorkflowEngine
from research_factory.workflows.primary import primary_steps

from .conftest import make_experiment


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("target", "index"), [("check_dataset", 1), ("audit_leakage", 4), ("statistical_review", 5)]
)
async def test_heavy_deterministic_checks_leave_the_event_loop_responsive(
    services: Services, monkeypatch: pytest.MonkeyPatch, target: str, index: int
) -> None:
    record, _ = services.ledger.freeze(make_experiment(), "researcher")
    selected = primary_steps()
    run = await WorkflowEngine(services, selected[:6]).start(record.experiment_id, "researcher")
    artifacts = {
        result.step: result.artifact_evidence_id
        for result in services.repos.steps.list(run.run_id)
        if result.artifact_evidence_id
    }
    ctx = StepContext(run, record, services, artifacts)
    release = threading.Event()
    original = getattr(steps, target)

    def slow(*args: Any, **kwargs: Any) -> Any:
        release.wait(2)
        return original(*args, **kwargs)

    monkeypatch.setattr(steps, target, slow)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError), anyio.fail_after(0.1):
            await selected[index].execute(ctx)
        assert time.monotonic() - started < 1
    finally:
        release.set()


def test_usage_reconciliation_requires_confirmation_and_preserves_audit(
    services: Services, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_services", lambda _: services)
    store = BudgetReservations(services.engine)
    call_id, _ = store.reserve(
        budgets=services.settings.budgets,
        run_id=None,
        step="Economic rationale review",
        model="fake",
        input_tokens=100,
        max_output_tokens=100,
        input_rate=1,
        output_rate=5,
        now=services.clock.now(),
        day=start_of_day(services.clock.now()),
    )
    store.uncertain(call_id)
    assert cli.main(["usage", "--pending"]) == 0
    assert call_id in capsys.readouterr().out
    args = [
        "reconcile-usage",
        call_id,
        "--actor",
        "operator",
        "--reason",
        "Provider receipt verified after worker stopped",
        "--model",
        "fake",
        "--input-tokens",
        "80",
        "--output-tokens",
        "20",
        "--cost-usd",
        "0.00018",
    ]
    assert cli.main(args) == 2
    assert len(store.outstanding()) == 1
    assert cli.main([*args, "--confirmed-finished"]) == 0
    assert store.outstanding() == []
    assert services.repos.usage.cost_since(start_of_day(services.clock.now())) == pytest.approx(0.00018)
    event = next(e for e in services.audit.events() if e.event_type == "model_usage_reconciled")
    assert event.actor == "operator" and event.payload["reservation_id"] == call_id
    assert cli.main([*args, "--confirmed-finished"]) == 2


def test_html_report_includes_escaped_approval_and_statistics() -> None:
    report: dict[str, Any] = {
        "run": {"run_id": "run_test", "status": "complete", "decision": "approve", "status_reason": None},
        "experiment": {
            "statement": "Test hypothesis",
            "feature": "momentum",
            "timing_basis": "acceptance",
            "dataset": "synthetic:v1",
            "trial_number": 1,
            "research_family": "test",
        },
        "steps": [],
        "findings": [],
        "audit": [],
        "gate": {"recommendation": "approve", "reasons": []},
        "statistics": {"n_obs": 252, "sharpe_annualized": 1.25},
        "approvals": [
            {
                "approver": "reviewer",
                "decision": "approve",
                "reason": "<script>fake</script>",
                "created_at": "2026-09-27",
            }
        ],
        "usage": {"tokens": 100, "cost_usd": 0.01},
        "prices_simulated_notice": "Prices are simulated.",
    }
    rendered = render_html(report)
    assert "<h2>Statistics</h2>" in rendered and "1.25" in rendered
    assert "<h2>Approvals</h2>" in rendered and "reviewer: approve" in rendered
    assert "<script>" not in rendered and "&lt;script&gt;fake&lt;/script&gt;" in rendered
