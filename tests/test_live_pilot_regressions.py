"""Regressions discovered by the first live pilot; no paid calls in tests."""

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest

from research_factory.config import Settings
from research_factory.domain.errors import TransientError
from research_factory.judgment import prompts
from research_factory.judgment.contract import (
    JudgmentValidationError,
    metric_catalog,
    output_schema,
    validate_output,
)
from research_factory.judgment.providers import AnthropicProvider, JudgmentRequest
from research_factory.persistence.budget import BudgetReservations
from research_factory.services.container import build_services


@pytest.mark.anyio
async def test_paid_response_survives_budget_stop_on_validation_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from research_factory.domain.errors import BudgetExceededError
    from research_factory.judgment.providers import JudgmentResponse
    from research_factory.workflows.primary import primary_engine

    from .conftest import make_experiment

    services = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    calls = 0

    def invoke(*args: Any) -> JudgmentResponse:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise BudgetExceededError("test retry cap")
        return JudgmentResponse(
            {"invalid": "retained paid output"}, "anthropic", "claude-opus-5", 10, 5, 0.001
        )

    monkeypatch.setattr(services.budget, "invoke", invoke)
    record, _ = services.ledger.freeze(make_experiment(), "alice")
    run = await primary_engine(services).start(record.experiment_id, "alice")
    assert "BUDGET_EXCEEDED" in (run.status_reason or "")
    events = [e for e in services.audit.events(run.run_id) if e.event_type == "model_response_received"]
    assert len(events) == 1
    assert events[0].payload["raw_output"] == {"invalid": "retained paid output"}


@pytest.mark.parametrize(
    "prose", ["Prices are simulated (ADR-0003).", "Inspect the original 10-K/A and 10-Q."]
)
def test_document_identifiers_are_not_measurements(prose: str) -> None:
    raw = {
        "verdict": "supported",
        "confidence": "high",
        "summary": prose,
        "claims": [{"kind": "risk", "statement": prose}],
    }
    validate_output(raw, verdicts=["supported"], allowed_evidence=set())
    for suffix in [" Sharpe is 999.", " Return is 4.02 percent.", " See ADR-0999."]:
        with pytest.raises(JudgmentValidationError, match="ungrounded number"):
            validate_output(
                {**raw, "summary": prose + suffix}, verdicts=["supported"], allowed_evidence=set()
            )


def test_metric_catalog_exposes_only_valid_fields_with_canonical_formats() -> None:
    documents = {
        "ev": {
            "n_obs": 300,
            "sharpe_annualized": 1.25,
            "newey_west_t": float("nan"),
            "deflated_sharpe": True,
            "arbitrary": 999,
        }
    }
    catalog = metric_catalog(documents)
    assert {r["field_path"]: r["format"] for r in catalog} == {"/n_obs": "d", "/sharpe_annualized": ".3f"}
    for row in catalog:
        raw = {
            "verdict": "supported",
            "confidence": "high",
            "summary": "A directly grounded metric follows.",
            "claims": [
                {
                    "kind": "calculation",
                    "statement": "{metric:0}",
                    "evidence_ids": ["ev"],
                    "metric_refs": [{k: row[k] for k in ("evidence_id", "field_path", "format")}],
                }
            ],
        }
        result = validate_output(
            raw, verdicts=["supported"], allowed_evidence={"ev"}, evidence_documents=documents
        )
        assert row["rendered_value"] in result.claims[0].statement


@pytest.mark.parametrize(
    ("task", "negative", "positive"),
    [
        ("point_in_time_review", "leakage", "clean"),
        ("economic_rationale", "unsupported", "supported"),
        ("implementation_review", "infeasible", "feasible"),
        ("research_committee", "reject", "approve"),
    ],
)
def test_blocking_attack_requires_task_specific_negative_verdict(
    task: str, negative: str, positive: str
) -> None:
    raw: dict[str, Any] = {
        "verdict": negative,
        "confidence": "high",
        "summary": "The supplied evidence establishes a blocking defect.",
        "claims": [{"kind": "fact", "statement": "The evidence shows leakage.", "evidence_ids": ["ev"]}],
        "attacks": [
            {
                "attack": "lookahead",
                "evidence_ids": ["ev"],
                "severity": "blocking",
                "status": "unrefuted",
                "criterion": "Must predate the decision.",
                "observation": "The filing arrived after the decision.",
            }
        ],
    }
    assert validate_output(raw, verdicts=prompts.VERDICTS[task], allowed_evidence={"ev"}).verdict == negative
    raw["verdict"] = positive
    with pytest.raises(JudgmentValidationError, match="blocking attack requires rejection"):
        validate_output(raw, verdicts=prompts.VERDICTS[task], allowed_evidence={"ev"})


@pytest.mark.parametrize("interrupted", [False, True])
def test_stream_settles_only_after_a_complete_response(interrupted: bool) -> None:
    calls: list[dict[str, Any]] = []

    def final() -> Any:
        if interrupted:
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
        return SimpleNamespace(
            model="claude-opus-5",
            usage=SimpleNamespace(input_tokens=100, output_tokens=40),
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text='{"ok":true}')],
        )

    @contextmanager
    def stream(**kwargs: Any) -> Any:
        calls.append(kwargs)
        yield SimpleNamespace(get_final_message=final)

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    provider = AnthropicProvider(client=client)
    services = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    request = JudgmentRequest("point_in_time_review", "Review.", {}, ["leakage"], output_schema(["leakage"]))
    if interrupted:
        with pytest.raises(TransientError):
            services.budget.invoke(provider, request, "pilot", "review", services.engine)
        assert services.repos.usage.totals_for_run("pilot") == (0, 0)
        assert BudgetReservations(services.engine).outstanding()[0]["status"] == "uncertain"
    else:
        response = services.budget.invoke(provider, request, "pilot", "review", services.engine)
        assert response.raw == {"ok": True}
        assert services.repos.usage.totals_for_run("pilot") == (140, 0.0015)
        assert not BudgetReservations(services.engine).outstanding()
    assert len(calls) == 1
    assert calls[0]["output_config"]["format"]["schema"] == request.schema
