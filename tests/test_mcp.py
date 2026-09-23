"""RSF-025 to RSF-031: the MCP surface, tested with the in-process client."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp import Client

from research_factory.auth import Principal, Role
from research_factory.server import create_server
from research_factory.services.container import Services

from .conftest import make_experiment

pytestmark = pytest.mark.anyio

EXPECTED_TOOLS = {
    "healthcheck",
    "get_filings_as_of",
    "get_prices_as_of",
    "get_universe_as_of",
    "freeze_hypothesis",
    "build_features",
    "run_backtest",
    "audit_leakage",
    "get_statistics",
    "start_run",
    "resume_run",
    "get_run_report",
    "list_runs",
    "approve_run",
    "get_ledger",
    "cancel_run",
}
AS_OF = "2023-12-30T00:00:00Z"


def _error(result: Any) -> dict[str, Any]:
    assert result.is_error
    text = result.content[0].text
    return json.loads(text[text.index("{") :])["error"]


def _frozen_args(**kw: Any) -> dict[str, Any]:
    exp = make_experiment(**kw)
    return {
        "hypothesis": exp.hypothesis.model_dump(mode="json"),
        "backtest": exp.backtest.model_dump(mode="json"),
    }


async def test_tool_surface_is_exact_and_has_no_trading(services: Services) -> None:
    async with Client(create_server(services)) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == EXPECTED_TOOLS
    assert not [n for n in tools if any(w in n for w in ("trade", "order", "broker", "delete"))]
    for tool in tools.values():
        assert tool.input_schema["type"] == "object"
        assert tool.description


async def test_healthcheck(services: Services) -> None:
    async with Client(create_server(services)) as client:
        result = await client.call_tool("healthcheck", {})
    assert result.is_error is False
    assert result.structured_content["status"] == "ok"


async def test_data_tools_require_as_of(services: Services) -> None:
    async with Client(create_server(services)) as client:
        missing = await client.call_tool("get_filings_as_of", {"security_id": "CIK0000320193"})
        naive = await client.call_tool(
            "get_filings_as_of", {"security_id": "CIK0000320193", "as_of": "2023-01-01T00:00:00"}
        )
        ok = await client.call_tool(
            "get_filings_as_of", {"security_id": "CIK0000320193", "as_of": "2021-01-01T00:00:00Z"}
        )
    assert _error(missing)["code"] == "AS_OF_REQUIRED"
    assert _error(naive)["code"] == "AS_OF_REQUIRED"
    data = ok.structured_content
    assert data["count"] > 0 and data["evidence_id"].startswith("ev_")
    assert all(f["accepted_at"] <= "2021-01-01T00:00:00+00:00" for f in data["filings"])


async def test_prices_and_universe(services: Services) -> None:
    async with Client(create_server(services)) as client:
        prices = await client.call_tool(
            "get_prices_as_of",
            {
                "security_ids": ["SYN001"],
                "start": "2021-01-04",
                "as_of": "2021-01-08T22:00:00Z",
                "dataset": "synthetic:v1",
            },
        )
        universe = await client.call_tool("get_universe_as_of", {"as_of": "2019-06-03T22:00:00Z"})
        unknown = await client.call_tool("get_universe_as_of", {"as_of": AS_OF, "dataset": "nope"})
    assert prices.structured_content["count"] == 5 and prices.structured_content["prices_simulated"] is True
    names = {s["security_id"] for s in universe.structured_content["securities"]}
    assert "CIK0001418091" in names  # Twitter: listed in 2019 even though it later delisted
    assert all(s["listed_to"] is None for s in universe.structured_content["securities"])  # future hidden
    assert _error(unknown)["code"] == "NOT_FOUND"


async def test_freeze_is_idempotent_and_counts_trials(services: Services) -> None:
    async with Client(create_server(services)) as client:
        a = (await client.call_tool("freeze_hypothesis", _frozen_args())).structured_content
        b = (await client.call_tool("freeze_hypothesis", _frozen_args())).structured_content
        c = (await client.call_tool("freeze_hypothesis", _frozen_args(cost=9.0))).structured_content
        ledger = (
            await client.call_tool("get_ledger", {"research_family": "earnings-drift"})
        ).structured_content
    assert a["created"] and not b["created"] and a["experiment_id"] == b["experiment_id"]
    assert c["trial_number"] == 2 and ledger["trials"] == 2


async def test_analysis_tools(services: Services) -> None:
    async with Client(create_server(services)) as client:
        exp = (await client.call_tool("freeze_hypothesis", _frozen_args())).structured_content[
            "experiment_id"
        ]
        leaky = (
            await client.call_tool("freeze_hypothesis", _frozen_args(timing="period_end"))
        ).structured_content["experiment_id"]
        bt = (await client.call_tool("run_backtest", {"experiment_id": exp})).structured_content
        stats = (await client.call_tool("get_statistics", {"experiment_id": exp})).structured_content
        audit = (await client.call_tool("audit_leakage", {"experiment_id": leaky})).structured_content
        missing = await client.call_tool("run_backtest", {"experiment_id": "exp_missing"})
    assert bt["run_status"] == "complete" and bt["artifact"]["summary"]["n_obs"] > 1000
    assert "net" not in bt["artifact"]  # bulky arrays stay in the evidence store
    assert stats["artifact"]["passed"] is True
    assert audit["run_status"] == "failed" and audit["artifact"]["blocking"] is True
    assert _error(missing)["code"] == "NOT_FOUND"


async def test_full_workflow_through_mcp_with_role_separation(services: Services) -> None:
    researcher = create_server(services, local_principal=Principal("alice", Role.RESEARCHER))
    approver = create_server(services, local_principal=Principal("bob", Role.APPROVER))
    async with Client(researcher) as client:
        exp = (await client.call_tool("freeze_hypothesis", _frozen_args())).structured_content[
            "experiment_id"
        ]
        run = (await client.call_tool("start_run", {"experiment_id": exp})).structured_content
        assert run["status"] == "needs_review" and run["current_step"] == "Research committee"
        forbidden = await client.call_tool(
            "approve_run", {"run_id": run["run_id"], "decision": "approve", "reason": "mine"}
        )
        assert _error(forbidden)["code"] == "FORBIDDEN"
        report = (await client.call_tool("get_run_report", {"run_id": run["run_id"]})).structured_content
        assert report["gate"]["recommendation"] == "approve"
    async with Client(approver) as client:
        freeze = await client.call_tool("freeze_hypothesis", _frozen_args(cost=3.0))
        assert _error(freeze)["code"] == "FORBIDDEN"  # approvers do not run research
        done = (
            await client.call_tool(
                "approve_run",
                {"run_id": run["run_id"], "decision": "approve", "reason": "Clean audit and statistics."},
            )
        ).structured_content
    assert done["status"] == "complete" and done["decision"] == "approve"


async def test_resources_and_prompts(services: Services) -> None:
    async with Client(create_server(services)) as client:
        policies = json.loads((await client.read_resource("project://policies")).contents[0].text)
        exp = (await client.call_tool("freeze_hypothesis", _frozen_args())).structured_content[
            "experiment_id"
        ]
        run = (await client.call_tool("start_run", {"experiment_id": exp})).structured_content
        report = json.loads((await client.read_resource(f"run://{run['run_id']}")).contents[0].text)
        ev_id = report["steps"][0]["artifact_evidence_id"]
        evidence = json.loads((await client.read_resource(f"evidence://{ev_id}")).contents[0].text)
        ledger = json.loads((await client.read_resource("ledger://earnings-drift")).contents[0].text)
        templates = {str(t.uri_template) for t in (await client.list_resource_templates()).resource_templates}
        prompts = {p.name for p in (await client.list_prompts()).prompts}
        prompt = await client.get_prompt("review_run", {"run_id": run["run_id"]})
    assert {r["id"] for r in policies["rules"]} >= {"no-trading", "as-of-required", "approval"}
    assert policies["statistical_thresholds"]["min_deflated_sharpe"] == 0.95
    assert report["run"]["run_id"] == run["run_id"]
    assert evidence["content"]["format"] == "rsf-frozen-hypothesis/1"
    assert ledger[0]["trial_number"] == 1
    assert templates == {"run://{run_id}", "evidence://{evidence_id}", "ledger://{research_family}"}
    assert prompts == {"review_run", "red_team_signal"}
    assert run["run_id"] in prompt.messages[0].content.text


async def test_tool_calls_are_audited_without_raw_arguments(services: Services) -> None:
    async with Client(create_server(services)) as client:
        await client.call_tool("get_ledger", {"research_family": "secret-family-name"})
        await client.call_tool("get_filings_as_of", {"security_id": "X"})
    events = [e for e in services.audit.events() if e.step == "mcp"]
    assert [e.event_type for e in events] == ["tool_call", "tool_error"]
    assert "secret-family-name" not in json.dumps([e.payload for e in events])
    assert events[1].payload["code"] == "AS_OF_REQUIRED"


async def test_errors_never_leak_internals(services: Services, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr(services.repos.experiments, "list_family", boom)
    async with Client(create_server(services)) as client:
        result = await client.call_tool("get_ledger", {"research_family": "x"})
    assert _error(result)["message"] == "internal error"
    assert "hunter2" not in result.content[0].text
