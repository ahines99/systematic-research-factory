"""The MCP server (RSF-025 to RSF-031).

One process exposes five capability modules, which can later become separate servers:
``sec_pit`` and ``market_data_pit`` (``data_tools``), and ``factor_research``, ``backtest``
and ``research_ledger`` (``research_tools``). Resources and prompts are registered here.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from pydantic import BaseModel, ValidationError

from .. import __version__
from ..auth import ApiKeyService, Principal
from ..domain.errors import InvalidInputError, NotFoundError
from ..domain.policies import POLICIES
from ..report import build_run_report
from ..services.container import Services
from . import data_tools, research_tools
from .common import ServerDeps, governed
from .research_tools import can_read_run

INSTRUCTIONS = """\
Systematic Research Factory: governed, point-in-time-clean equity research.
Read project://policies first. Every data query needs a timezone-aware as_of. Numbers come
only from tools; cite the evidence_id each tool returns. Freeze a hypothesis before testing
it: every frozen variant counts as a trial. Committee decisions are recorded by a human
approver with approve_run. There are no trading tools."""


class Health(BaseModel):
    status: str
    version: str


class GovernedMCPServer(MCPServer):
    """Normalize only the SDK's proven input-validation failure, never arbitrary errors."""

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: Context[Any, Any] | None = None
    ) -> Any:
        try:
            return await super().call_tool(name, arguments, context)
        except ToolError as exc:
            if type(exc) is ToolError and isinstance(exc.__cause__, ValidationError):
                error = InvalidInputError(
                    "tool arguments failed schema validation",
                    details={"fields": [".".join(str(p) for p in e["loc"]) for e in exc.__cause__.errors()]},
                )
                raise ToolError(json.dumps({"error": error.to_dict()})) from None
            raise


async def governed_resource(*args: Any) -> str:
    """Resources report policy errors as ResourceError with the same typed JSON body as tools."""
    try:
        result: str = await governed(*args)
    except ToolError as exc:
        raise ResourceError(str(exc)) from None
    return result


def create_server(services: Services, *, local_principal: Principal | None = None) -> MCPServer:
    deps = ServerDeps(services=services, keys=ApiKeyService(services.repos.api_keys, services.clock))
    if local_principal is not None:
        deps.local_principal = local_principal
    mcp = GovernedMCPServer("Systematic Research Factory", version=__version__, instructions=INSTRUCTIONS)

    @mcp.tool(description="Service health for diagnostics.")
    async def healthcheck(ctx: Context[Any, Any] | None = None) -> Health:
        async def body(_: Principal) -> Health:
            return Health(status="ok", version=__version__)

        return await governed(deps, ctx, "healthcheck", "healthcheck", {}, body)

    data_tools.register(mcp, deps)
    research_tools.register(mcp, deps)

    @mcp.resource(
        "project://policies",
        mime_type="application/json",
        description="Operating policies enforced by the server.",
    )
    async def policies() -> str:
        doc = {
            **POLICIES,
            "statistical_thresholds": services.settings.thresholds.model_dump(),
            "budgets": services.settings.budgets.model_dump(),
        }
        return json.dumps(doc, indent=1, sort_keys=True)

    @mcp.resource("run://{run_id}", mime_type="application/json", description="Structured report for a run.")
    async def run_resource(run_id: str, ctx: Context[Any, Any] | None = None) -> str:
        async def body(principal: Principal) -> str:
            run = services.repos.runs.get(run_id)
            if run is None or not can_read_run(principal, run):
                raise NotFoundError(f"run {run_id} not found")
            return json.dumps(build_run_report(services, run_id), indent=1)

        return await governed_resource(deps, ctx, "run://", "read_demo_runs", {"run_id": run_id}, body)

    @mcp.resource(
        "evidence://{evidence_id}",
        mime_type="application/json",
        description="Evidence record and, for small JSON, its content.",
    )
    async def evidence_resource(evidence_id: str, ctx: Context[Any, Any] | None = None) -> str:
        async def body(_: Principal) -> str:
            ref = services.evidence.get(evidence_id)
            doc: dict[str, Any] = {"record": ref.model_dump(mode="json")}
            if ref.metadata.get("bytes", 0) <= 200_000 and ref.source_type != "dataset_snapshot":
                try:
                    doc["content"] = services.evidence.load_json(evidence_id)
                except ValueError:
                    doc["content"] = None
            return json.dumps(doc, indent=1)

        return await governed_resource(
            deps, ctx, "evidence://", "read_evidence", {"evidence_id": evidence_id}, body
        )

    @mcp.resource(
        "ledger://{research_family}", mime_type="application/json", description="Trials in a research family."
    )
    async def ledger_resource(research_family: str, ctx: Context[Any, Any] | None = None) -> str:
        async def body(_: Principal) -> str:
            records = services.repos.experiments.list_family(research_family)
            return json.dumps(
                [
                    {
                        "experiment_id": r.experiment_id,
                        "trial_number": r.trial_number,
                        "sharpe_per_period": r.sharpe_per_period,
                    }
                    for r in records
                ],
                indent=1,
            )

        return await governed_resource(
            deps, ctx, "ledger://", "read_ledger", {"research_family": research_family}, body
        )

    @mcp.prompt(description="Review a workflow run, separating facts, assumptions and recommendations.")
    def review_run(run_id: str) -> str:
        return (
            f"Review workflow run {run_id}. Read run://{run_id} and project://policies first. "
            "Separate facts, calculations, assumptions, risks and recommendations. Cite an evidence ID for every "
            "material claim, never compute numbers yourself, and say NEEDS_EVIDENCE where support is missing. "
            "Follow the research-committee Skill."
        )

    @mcp.prompt(description="Red-team a frozen experiment for leakage, overfitting and fragility.")
    def red_team_signal(experiment_id: str) -> str:
        return (
            f"Red-team experiment {experiment_id} using the signal-red-team Skill. For each attack (leakage, data "
            "snooping, regime dependence, crowding, capacity, cost sensitivity, concentration, execution delay, "
            "survivorship, restatement) call the relevant tool, cite evidence IDs, and report severity and whether "
            "the attack was refuted. Never mutate the experiment: every variant is a new frozen trial."
        )

    return mcp


__all__ = ["create_server"]
