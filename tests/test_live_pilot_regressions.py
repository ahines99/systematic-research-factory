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
