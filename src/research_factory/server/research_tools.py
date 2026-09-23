"""``factor_research``, ``backtest`` and ``research_ledger`` capability modules.

Analysis tools (``build_features``, ``run_backtest``, ``audit_leakage``, ``get_statistics``)
run the deterministic prefix of the workflow as an auditable ``analysis`` run and return its
artifact. ``start_run`` runs the full nine-step workflow.
"""

from __future__ import annotations

from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import BaseModel, Field

from ..auth import Principal
from ..domain.errors import NotFoundError
from ..domain.project_models import ApprovalDecision, BacktestSpec, Experiment, Hypothesis
from ..report import build_run_report
from ..workflows.engine import WorkflowEngine
from ..workflows.primary import primary_engine, primary_steps
from .common import DEMO_REQUESTERS, ServerDeps, governed

ANALYSIS_STEPS = {"build_features": 3, "run_backtest": 4, "audit_leakage": 5, "get_statistics": 6}
ARTIFACT_STEP = {
    "build_features": "Feature build",
    "run_backtest": "Backtest",
    "audit_leakage": "Leakage audit",
    "get_statistics": "Statistical review",
}


class FrozenExperiment(BaseModel):
    experiment_id: str
    research_family: str
    trial_number: int
    created: bool = Field(description="False when an identical experiment was already frozen")
    note: str


class AnalysisResult(BaseModel):
    run_id: str
    run_status: str
    experiment_id: str
    step: str
    artifact_evidence_id: str | None
    artifact: dict[str, Any] | None
    findings: list[dict[str, Any]]


class RunSummary(BaseModel):
    run_id: str
    experiment_id: str
    project_type: str
    status: str
    current_step: str | None
    status_reason: str | None
    decision: str | None
    requested_by: str


class RunList(BaseModel):
    runs: list[RunSummary]


class LedgerEntry(BaseModel):
    experiment_id: str
    trial_number: int
    hypothesis_id: str
    sharpe_per_period: float | None
    created_at: str


class Ledger(BaseModel):
    research_family: str
    trials: int
    entries: list[LedgerEntry]


def _summary(run: Any) -> RunSummary:
    return RunSummary(
        run_id=run.run_id,
        experiment_id=run.experiment_id,
        project_type=run.project_type,
        status=str(run.status),
        current_step=run.current_step,
        status_reason=run.status_reason,
        decision=str(run.decision) if run.decision else None,
        requested_by=run.requested_by,
    )


def can_read_run(principal: Principal, run: Any) -> bool:
    return not principal.is_guest or run.requested_by in DEMO_REQUESTERS


def lean_artifact(artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop bulky arrays from tool output; the full artifact stays in the evidence store."""
    if artifact is None:
        return None
    bulky = {
        "values",
        "lineage",
        "universe",
        "gross",
        "net",
        "positions",
        "universe_by_decision",
        "ic_by_decision",
        "turnover",
        "sessions",
    }
    return {k: v for k, v in artifact.items() if k not in bulky}


def register(mcp: MCPServer, deps: ServerDeps) -> None:
    services = deps.services

    @mcp.tool(
        description="Freeze a hypothesis and backtest spec as an immutable experiment in the research ledger."
    )
    async def freeze_hypothesis(
        hypothesis: Hypothesis, backtest: BacktestSpec, ctx: Context[Any, Any] | None = None
    ) -> FrozenExperiment:
        async def body(principal: Principal) -> FrozenExperiment:
            experiment = Experiment(hypothesis=hypothesis, backtest=backtest)
            record, created = services.ledger.freeze(experiment, principal.name)
            note = (
                f"Frozen as trial {record.trial_number} of '{record.research_family}'."
                if created
                else "This exact experiment was already frozen; no new trial was added."
            )
            return FrozenExperiment(
                experiment_id=record.experiment_id,
                research_family=record.research_family,
                trial_number=record.trial_number,
                created=created,
                note=note,
            )

        return await governed(
            deps,
            ctx,
            "freeze_hypothesis",
            "freeze_hypothesis",
            {"hypothesis_id": hypothesis.hypothesis_id},
            body,
        )

    def _analysis_tool(name: str) -> None:
        async def tool(experiment_id: str, ctx: Context[Any, Any] | None = None) -> AnalysisResult:
            async def body(principal: Principal) -> AnalysisResult:
                steps = primary_steps()[: ANALYSIS_STEPS[name]]
                run = await WorkflowEngine(services, steps).start(
                    experiment_id, principal.name, project_type="analysis"
                )
                step = ARTIFACT_STEP[name]
                result = services.repos.steps.get(run.run_id, step)
                artifact = (
                    services.evidence.load_json(result.artifact_evidence_id)
                    if result and result.artifact_evidence_id
                    else None
                )
                findings = [
                    f.model_dump(mode="json") for f in services.repos.findings.list_for_run(run.run_id)
                ]
                return AnalysisResult(
                    run_id=run.run_id,
                    run_status=str(run.status),
                    experiment_id=experiment_id,
                    step=step,
                    artifact_evidence_id=result.artifact_evidence_id if result else None,
                    artifact=lean_artifact(artifact),
                    findings=findings,
                )

            return await governed(deps, ctx, name, "run_analysis", {"experiment_id": experiment_id}, body)

        tool.__name__ = name
        descriptions = {
            "build_features": "Build the experiment's feature with knowledge-time lineage (deterministic).",
            "run_backtest": "Run the experiment's deterministic backtest and record the result in the ledger.",
            "audit_leakage": "Audit the experiment for look-ahead, survivorship, execution-delay and target leakage.",
            "get_statistics": "Statistical review: Sharpe, Newey-West t, bootstrap CI, deflated Sharpe with the ledger's trial count.",
        }
        mcp.tool(name=name, description=descriptions[name])(tool)

    for name in ANALYSIS_STEPS:
        _analysis_tool(name)

    @mcp.tool(
        description="Start the full nine-step research workflow. It pauses for a human committee decision."
    )
    async def start_run(experiment_id: str, ctx: Context[Any, Any] | None = None) -> RunSummary:
        async def body(principal: Principal) -> RunSummary:
            return _summary(await primary_engine(services).start(experiment_id, principal.name))

        return await governed(deps, ctx, "start_run", "start_run", {"experiment_id": experiment_id}, body)

    @mcp.tool(
        description="Resume a paused run (after an approval, an outage, or a budget reset). Completed steps are reused."
    )
    async def resume_run(run_id: str, ctx: Context[Any, Any] | None = None) -> RunSummary:
        async def body(principal: Principal) -> RunSummary:
            return _summary(await primary_engine(services).advance(run_id, principal.name))

        return await governed(deps, ctx, "resume_run", "resume_run", {"run_id": run_id}, body)

    @mcp.tool(
        description="Structured report for a run: steps, findings with evidence, gate, approvals, audit trail."
    )
    async def get_run_report(run_id: str, ctx: Context[Any, Any] | None = None) -> dict[str, Any]:
        async def body(principal: Principal) -> dict[str, Any]:
            run = services.repos.runs.get(run_id)
            if run is None or not can_read_run(principal, run):
                raise NotFoundError(f"run {run_id} not found")
            return build_run_report(services, run_id)

        action = "read_demo_runs"
        return await governed(deps, ctx, "get_run_report", action, {"run_id": run_id}, body)

    @mcp.tool(description="Most recent runs, newest first.")
    async def list_runs(
        limit: int = Field(default=20, ge=1, le=100), ctx: Context[Any, Any] | None = None
    ) -> RunList:
        async def body(principal: Principal) -> RunList:
            runs = [r for r in services.repos.runs.list(limit=limit * 3) if can_read_run(principal, r)][
                :limit
            ]
            return RunList(runs=[_summary(r) for r in runs])

        return await governed(deps, ctx, "list_runs", "read_demo_runs", {"limit": limit}, body)

    @mcp.tool(
        description="Record the research committee decision (approver role; not the run's requester), then resume the run."
    )
    async def approve_run(
        run_id: str,
        decision: Literal["approve", "reject", "needs_more_evidence"],
        reason: str = Field(min_length=3, max_length=2000),
        ctx: Context[Any, Any] | None = None,
    ) -> RunSummary:
        async def body(principal: Principal) -> RunSummary:
            services.approvals.record(
                run_id=run_id,
                approver=principal.name,
                role=str(principal.role),
                decision=ApprovalDecision(decision),
                reason=reason,
            )
            return _summary(await primary_engine(services).advance(run_id, principal.name))

        return await governed(
            deps, ctx, "approve_run", "approve_run", {"run_id": run_id, "decision": decision}, body
        )

    @mcp.tool(description="All frozen experiments (trials) in a research family, with recorded results.")
    async def get_ledger(research_family: str, ctx: Context[Any, Any] | None = None) -> Ledger:
        async def body(_: Principal) -> Ledger:
            records = services.repos.experiments.list_family(research_family)
            return Ledger(
                research_family=research_family,
                trials=len(records),
                entries=[
                    LedgerEntry(
                        experiment_id=r.experiment_id,
                        trial_number=r.trial_number,
                        hypothesis_id=r.experiment.hypothesis.hypothesis_id,
                        sharpe_per_period=r.sharpe_per_period,
                        created_at=r.created_at.isoformat(),
                    )
                    for r in records
                ],
            )

        return await governed(
            deps, ctx, "get_ledger", "read_ledger", {"research_family": research_family}, body
        )
