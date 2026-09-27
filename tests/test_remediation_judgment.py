"""Adversarial numeric grounding and model-budget lifecycle regressions (offline)."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from sqlalchemy import select

from research_factory.config import Budgets, Settings
from research_factory.domain.errors import (
    BudgetExceededError,
    InvalidInputError,
    NeedsEvidenceError,
    NotFoundError,
)
from research_factory.judgment.contract import JudgmentValidationError, output_schema, validate_output
from research_factory.judgment.providers import (
    AnthropicProvider,
    JudgmentRequest,
    JudgmentResponse,
    RulesProvider,
)
from research_factory.persistence.budget import BudgetReservations, model_reservations
from research_factory.persistence.db import make_engine
from research_factory.services.budget import BudgetGuard
from research_factory.services.container import build_services
from research_factory.workflows.primary import primary_engine

from .conftest import make_experiment


def output(statement: str, refs: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "verdict": "supported",
        "confidence": "medium",
        "summary": "The supplied evidence was reviewed.",
        "claims": [
            {
                "kind": "calculation",
                "statement": statement,
                "evidence_ids": ["ev_real"],
                "metric_refs": refs or [],
            }
        ],
        "open_questions": [],
        "needs_evidence": False,
    }


def request() -> JudgmentRequest:
    return JudgmentRequest(
        "economic_rationale", "Review evidence.", {}, ["supported"], output_schema(["supported"])
    )


def test_fabricated_number_with_real_citation_fails() -> None:
    with pytest.raises(JudgmentValidationError, match="ungrounded number"):
        validate_output(
            output("Sharpe is 999."),
            verdicts=["supported"],
            allowed_evidence={"ev_real"},
            evidence_documents={"ev_real": {"sharpe_annualized": 1.2}},
        )


def test_metric_identity_and_value_are_rendered_from_artifact() -> None:
    refs = [{"evidence_id": "ev_real", "field_path": "/n_obs", "format": "d"}]
    with pytest.raises(JudgmentValidationError, match="labels are rendered by code"):
        validate_output(
            output("Sharpe is {metric:0}", refs),
            verdicts=["supported"],
            allowed_evidence={"ev_real"},
            evidence_documents={"ev_real": {"n_obs": 999}},
        )
    valid = validate_output(
        output("{metric:0}", refs),
        verdicts=["supported"],
        allowed_evidence={"ev_real"},
        evidence_documents={"ev_real": {"n_obs": 999}},
    )
    assert valid.claims[0].statement == "Number of observations (/n_obs): 999"


def test_calculation_channel_rejects_spelled_out_numbers_and_false_units() -> None:
    with pytest.raises(JudgmentValidationError, match="structured metric_refs"):
        validate_output(
            output("Sharpe is nine hundred."), verdicts=["supported"], allowed_evidence={"ev_real"}
        )
    refs = [{"evidence_id": "ev_real", "field_path": "/n_obs", "format": ".2%"}]
    with pytest.raises(JudgmentValidationError, match="numeric artifact field"):
        validate_output(
            output("{metric:0}", refs),
            verdicts=["supported"],
            allowed_evidence={"ev_real"},
            evidence_documents={"ev_real": {"n_obs": 999}},
        )


@pytest.mark.parametrize("doc", [{}, {"n_obs": "999"}, {"n_obs": float("nan")}, {"n_obs": True}])
def test_metric_reference_requires_finite_numeric_field(doc: dict[str, Any]) -> None:
    refs = [{"evidence_id": "ev_real", "field_path": "/n_obs", "format": "d"}]
    with pytest.raises(JudgmentValidationError, match="numeric artifact field"):
        validate_output(
            output("{metric:0}", refs),
            verdicts=["supported"],
            allowed_evidence={"ev_real"},
            evidence_documents={"ev_real": doc},
        )


@pytest.mark.parametrize(
    "backend",
    [
        "sqlite",
        pytest.param(
            "postgres",
            marks=[
                pytest.mark.postgres,
                pytest.mark.skipif(
                    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
                    reason="needs PostgreSQL test database",
                ),
            ],
        ),
    ],
)
def test_reservations_serialize_across_independent_database_connections(tmp_path: Any, backend: str) -> None:
    url = f"sqlite:///{tmp_path / 'budget.db'}"
    if backend == "postgres":
        from .test_postgres import _services

        url = os.environ["DATABASE_URL"]
        s = _services()
    else:
        s = build_services(Settings(database_url=url, blob_store="memory://"))
    other = make_engine(url)
    budgets = Budgets(max_cost_usd_per_run=0.001, max_cost_usd_per_day=0.001)
    barrier = threading.Barrier(2)

    def attempt(engine: Any, run: str) -> str:
        barrier.wait()
        try:
            return BudgetReservations(engine).reserve(
                budgets=budgets,
                run_id=run,
                step="review",
                model="fake",
                input_tokens=100,
                max_output_tokens=100,
                input_rate=5,
                output_rate=5,
                now=datetime.now(UTC),
                day=datetime(2020, 1, 1, tzinfo=UTC),
            )[0]
        except BudgetExceededError:
            return "blocked"

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(attempt, s.engine, "first")
        second = pool.submit(attempt, other, "second")
        outcomes = [first.result(), second.result()]
    assert outcomes.count("blocked") == 1


def test_tiny_budget_prevents_dispatch() -> None:
    calls: list[Any] = []
    provider = SimpleNamespace(name="paid", model="fake", judge=lambda req: calls.append(req))
    s = build_services(
        Settings(
            database_url="sqlite://",
            blob_store="memory://",
            budgets=Budgets(max_cost_usd_per_day=0.01, max_cost_usd_per_run=0.01),
        )
    )
    with pytest.raises(BudgetExceededError):
        s.budget.invoke(provider, request(), "run", "review", s.engine)
    assert not calls
    assert s.repos.usage.totals_for_run("run") == (0, 0)


@pytest.mark.parametrize("stop", ["refusal", "end_turn"])
def test_refusal_and_empty_response_still_record_paid_usage(stop: str) -> None:
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        model="claude-opus-5",
        stop_reason=stop,
        content=[],
    )
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response)))
    provider = AnthropicProvider(client=client)
    s = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    with pytest.raises(NeedsEvidenceError):
        s.budget.invoke(provider, request(), "run", "review", s.engine)
    assert s.repos.usage.totals_for_run("run") == (1200, 0.01)


@pytest.mark.anyio
async def test_late_response_is_accounted_and_pending_call_cannot_retry() -> None:
    returned = threading.Event()
    entered = threading.Event()
    calls: list[Any] = []

    def judge(req: Any) -> JudgmentResponse:
        calls.append(req)
        entered.set()
        time.sleep(0.15)
        returned.set()
        return JudgmentResponse({}, "fake", "fake", 1000, 200, 0.01)

    s = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    provider = SimpleNamespace(name="paid", model="fake", judge=judge)
    with pytest.raises(TimeoutError), anyio.fail_after(0.04):
        await anyio.to_thread.run_sync(
            s.budget.invoke, provider, request(), "run", "review", s.engine, abandon_on_cancel=True
        )
    assert entered.is_set()
    with pytest.raises(BudgetExceededError, match="pending or uncertain"):
        s.budget.invoke(provider, request(), "run", "review", s.engine)
    await anyio.to_thread.run_sync(returned.wait)
    # The event precedes transactional settlement by a few instructions.
    for _ in range(100):
        if s.repos.usage.totals_for_run("run")[0]:
            break
        await anyio.sleep(0.005)
    assert len(calls) == 1
    assert s.repos.usage.totals_for_run("run") == (1200, 0.01)


def test_ambiguous_failure_stays_reserved_until_reconciled() -> None:
    def fail(req: Any) -> Any:
        raise TimeoutError("connection lost")

    s = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    provider = SimpleNamespace(name="paid", model="fake", judge=fail)
    with pytest.raises(TimeoutError):
        s.budget.invoke(provider, request(), "run", "review", s.engine)
    with pytest.raises(BudgetExceededError, match="pending or uncertain"):
        s.budget.invoke(provider, request(), "run", "review", s.engine)
    with s.engine.connect() as conn:
        row = conn.execute(select(model_reservations)).mappings().one()
    assert row["status"] == "uncertain"
    ledger = BudgetReservations(s.engine)
    ledger.settle(
        row["reservation_id"],
        now=s.clock.now(),
        model="fake",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.005,
    )
    ledger.settle(
        row["reservation_id"],
        now=s.clock.now(),
        model="fake",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.005,
    )
    assert s.repos.usage.totals_for_run("run") == (120, 0.005)


def test_operator_reconciliation_is_explicit_and_audited() -> None:
    s = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    ledger = BudgetReservations(s.engine)
    now = s.clock.now()
    call_id, _ = ledger.reserve(
        budgets=s.settings.budgets,
        run_id="run",
        step="review",
        model="fake",
        input_tokens=100,
        max_output_tokens=100,
        input_rate=5,
        output_rate=5,
        now=now,
        day=now,
    )
    assert ledger.outstanding()[0]["reservation_id"] == call_id
    args = dict(
        actor="operator",
        reason="Provider billing receipt verified after worker exit.",
        now=now,
        model="fake",
        input_tokens=100,
        output_tokens=20,
        cost_usd=0.005,
    )
    with pytest.raises(InvalidInputError, match="confirmation"):
        ledger.reconcile(call_id, confirmed_finished=False, **args)
    with pytest.raises(NotFoundError):
        ledger.reconcile("missing", confirmed_finished=True, **args)
    ledger.reconcile(call_id, confirmed_finished=True, **args)
    with pytest.raises(InvalidInputError, match="already settled"):
        ledger.reconcile(call_id, confirmed_finished=True, **args)
    assert not ledger.outstanding()
    assert s.repos.usage.totals_for_run("run") == (120, 0.005)
    assert s.audit.events("run")[-1].event_type == "model_usage_reconciled"


def test_counting_uses_full_request_and_limits_generation_to_reserved_allowance() -> None:
    counted: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []

    def count(**kwargs: Any) -> Any:
        counted.append(kwargs)
        return SimpleNamespace(input_tokens=1500)

    def generate(**kwargs: Any) -> Any:
        generated.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1500, output_tokens=100),
            model="claude-opus-5",
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="{}")],
        )

    client = SimpleNamespace(
        beta=SimpleNamespace(messages=SimpleNamespace(count_tokens=count, create=generate))
    )
    s = build_services(
        Settings(
            database_url="sqlite://",
            blob_store="memory://",
            budgets=Budgets(max_cost_usd_per_run=0.10, max_cost_usd_per_day=0.10),
        )
    )
    req = replace(request(), system="Full skill text " * 10000, feedback=("Feedback included",))
    s.budget.invoke(AnthropicProvider(client=client), req, "run", "review", s.engine)
    assert counted[0]["system"] == req.system
    assert counted[0]["messages"] == generated[0]["messages"]
    assert counted[0]["output_config"] == generated[0]["output_config"]
    assert 256 <= generated[0]["max_tokens"] < 16000


@pytest.mark.anyio
async def test_needs_evidence_overrides_feasible_verdict() -> None:
    class Missing(RulesProvider):
        def judge(self, req: JudgmentRequest) -> JudgmentResponse:
            response = super().judge(req)
            if req.step_slug == "implementation_review":
                response.raw["needs_evidence"] = True
            return replace(response, input_tokens=0, output_tokens=0)

    s = build_services(
        Settings(
            database_url="sqlite://",
            blob_store="memory://",
            budgets=Budgets(
                max_tokens_per_run=1000000, max_cost_usd_per_run=100.0, max_cost_usd_per_day=100.0
            ),
        ),
        provider=Missing(),
    )
    rec, _ = s.ledger.freeze(make_experiment(), "alice")
    run = await primary_engine(s).start(rec.experiment_id, "alice")
    assert run.current_step == "Implementation review"
    assert (run.status_reason or "").startswith("NEEDS_EVIDENCE")
    assert s.approvals.pending_gate(run.run_id).recommendation == "needs_more_evidence"


def test_isolated_cases_share_durable_daily_spend(tmp_path: Any) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'shared-spend.db'}", blob_store="memory://")
    owner = build_services(settings)
    limits = Budgets(max_cost_usd_per_run=0.05, max_cost_usd_per_day=0.05)
    calls: list[dict[str, Any]] = []

    def generate(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=1000, output_tokens=kwargs["max_tokens"]),
            model="claude-fable-5-1",
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="{}")],
        )

    provider = AnthropicProvider(
        model="claude-fable-5-1",
        client=SimpleNamespace(
            beta=SimpleNamespace(
                messages=SimpleNamespace(
                    count_tokens=lambda **kwargs: SimpleNamespace(input_tokens=1000),
                    create=generate,
                )
            )
        ),
    )
    first = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    first.budget = BudgetGuard(
        limits, owner.repos.usage, first.repos.runs, first.clock, accounting_engine=owner.engine
    )
    first.budget.invoke(provider, request(), "case-first", "review", first.engine)
    assert owner.repos.usage.totals_for_run("case-first")[1] > 0
    assert first.repos.usage.totals_for_run("case-first") == (0, 0.0)

    # A new case and new accounting Engine cannot reset the owner's UTC-day cap.
    owner.engine.dispose()
    owner = build_services(settings)
    second = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    second.budget = BudgetGuard(
        limits, owner.repos.usage, second.repos.runs, second.clock, accounting_engine=owner.engine
    )
    with pytest.raises(BudgetExceededError, match="insufficient unreserved budget"):
        second.budget.invoke(provider, request(), "case-second", "review", second.engine)
    assert len(calls) == 1
    assert second.budget.spent_today() == owner.repos.usage.totals_for_run("case-first")[1]


def test_pending_accounting_reservation_survives_service_recreation(tmp_path: Any) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'pending-spend.db'}", blob_store="memory://")
    owner = build_services(settings)
    now = owner.clock.now()
    limits = Budgets(max_cost_usd_per_run=1, max_cost_usd_per_day=1)
    reservation_id, _ = BudgetReservations(owner.engine).reserve(
        budgets=limits,
        run_id="unfinished-case",
        step="review",
        model="fake",
        input_tokens=100,
        max_output_tokens=100,
        input_rate=5000,
        output_rate=5000,
        now=now,
        day=now,
    )
    owner.engine.dispose()
    recreated = build_services(settings)
    case = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    case.budget = BudgetGuard(
        limits, recreated.repos.usage, case.repos.runs, case.clock, accounting_engine=recreated.engine
    )
    calls: list[Any] = []
    provider = SimpleNamespace(name="paid", model="fake", judge=lambda req: calls.append(req))
    with pytest.raises(BudgetExceededError, match="pending or uncertain"):
        case.budget.invoke(provider, request(), "unfinished-case", "review", case.engine)
    with pytest.raises(BudgetExceededError, match="daily model-spend cap"):
        case.budget.invoke(provider, request(), "new-case", "review", case.engine)
    assert calls == []
    assert BudgetReservations(recreated.engine).outstanding()[0]["reservation_id"] == reservation_id
