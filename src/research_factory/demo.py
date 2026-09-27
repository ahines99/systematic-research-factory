"""Demo scenarios, pre-recorded runs and exact replay (RSF-048, RSF-077, RSF-082).

``record_demo`` runs a curated set of scenarios end to end: the success path, controlled
failures, an overfit rejection and a survived fault. The resulting runs are what guests
browse on the public demo, so live model calls are rarely needed.

``replay_run`` re-executes a run's deterministic steps from the dataset snapshot archived
with it and checks that every artifact is byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from .domain.errors import ConflictError
from .domain.project_models import (
    ApprovalDecision,
    BacktestSpec,
    Experiment,
    FeatureSpec,
    Hypothesis,
    UniverseSpec,
)
from .services.container import Services
from .workflows.engine import WorkflowEngine
from .workflows.execution import runtime_identity
from .workflows.faults import FaultRule
from .workflows.primary import primary_engine, primary_steps

DEMO_REQUESTER = "demo-researcher"
DEMO_APPROVER = "demo-approver"
DETERMINISTIC_STEPS = 6  # the two subsequent review steps may call a paid model
RATIONALE = (
    "Investors under-react to earnings news, so prices keep drifting in the direction of the surprise "
    "for several weeks after the filing becomes public."
)


def demo_experiment(
    hypothesis_id: str,
    *,
    family: str = "earnings-drift",
    dataset: str = "synthetic:v1",
    timing: str = "acceptance",
    universe: str = "point_in_time",
    feature: str = "eps_yoy_change",
    delay: int = 30,
    cost: float = 5.0,
    hold: int = 20,
    rationale: str = RATIONALE,
    statement: str = "Companies whose EPS rose year over year outperform after the filing is accepted.",
    start: str = "2019-06-03",
    end: str = "2023-12-29",
) -> Experiment:
    return Experiment(
        hypothesis=Hypothesis(
            hypothesis_id=hypothesis_id,
            research_family=family,
            statement=statement,
            rationale=rationale,
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
            feature=FeatureSpec(name=feature, timing_basis=timing),
            universe=UniverseSpec(dataset=dataset, mode=universe),
            horizon_days=hold,
        ),
        backtest=BacktestSpec(
            hypothesis_id=hypothesis_id,
            start=date.fromisoformat(start),
            end=date.fromisoformat(end),
            as_of=datetime(2023, 12, 30, tzinfo=UTC),
            execution_delay_minutes=delay,
            transaction_cost_bps=cost,
            hold_days=hold,
        ),
    )


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    experiment: Experiment
    prior_trials: int = 0
    faults: tuple[str, ...] = ()
    decide: bool = True  # record the committee decision the gate allows
    story: str = ""


def scenarios() -> list[Scenario]:
    return [
        Scenario(
            "clean-approved",
            "Clean research, approved",
            demo_experiment("eps-drift"),
            story="Acceptance-timed EPS signal, point-in-time universe, realistic delay and costs. Every check passes; a human approves.",
        ),
        Scenario(
            "leak-caught",
            "Look-ahead leak caught",
            demo_experiment("eps-drift-period-end", timing="period_end"),
            story="The same idea, but EPS is treated as known at the fiscal period end. The backtest looks better; the leakage audit fails the run.",
        ),
        Scenario(
            "survivorship-caught",
            "Survivorship bias caught",
            demo_experiment("eps-drift-survivors", universe="current_constituents"),
            story="Only companies still listed at the end are tested. The audit finds the missing delisted names.",
        ),
        Scenario(
            "overfit-rejected",
            "Overfit signal rejected",
            demo_experiment(
                "eps-drift-variant-100", dataset="synthetic:v1:weak", family="earnings-drift-search"
            ),
            prior_trials=99,
            story="A weak signal found after 99 other variants. Alone it looks significant; the deflated Sharpe ratio rejects it.",
        ),
        Scenario(
            "real-filings",
            "Real SEC filings",
            demo_experiment("eps-drift-edgar", dataset="edgar-semi:v1", family="earnings-drift-edgar"),
            story="Real EDGAR acceptance times, restatements and delistings for 44 companies, with simulated prices.",
        ),
        Scenario(
            "fault-survived",
            "Data outage survived",
            demo_experiment("eps-drift", cost=5.0),
            faults=("data_source:timeout:1",),
            story="The data source times out once. The step is retried and the run completes.",
        ),
    ]


def _freeze_prior_trials(services: Services, scenario: Scenario, requester: str = DEMO_REQUESTER) -> None:
    for k in range(scenario.prior_trials):
        variant = demo_experiment(
            f"variant-{k:03d}",
            family=scenario.experiment.hypothesis.research_family,
            dataset=scenario.experiment.hypothesis.universe.dataset,
            delay=31 + k,
        )
        services.ledger.freeze(variant, requester)


@dataclass
class ScenarioResult:
    scenario: str
    run_id: str
    status: str
    current_step: str | None
    decision: str | None
    gate: str | None
    status_reason: str | None
    artifacts: dict[str, str] = field(default_factory=dict)  # step -> artifact content hash


def artifact_hashes(services: Services, run_id: str, limit: int = 8) -> dict[str, str]:
    names = [s.name for s in primary_steps()[:limit]]
    out = {}
    for result in services.repos.steps.list(run_id):
        if result.step in names and result.artifact_evidence_id:
            out[result.step] = services.evidence.get(result.artifact_evidence_id).content_hash
    return out


async def run_scenario(
    services: Services, scenario: Scenario, requester: str = DEMO_REQUESTER, decide: bool | None = None
) -> ScenarioResult:
    """Run one scenario exactly as designed: prior trials are frozen first, so trial counts match."""
    _freeze_prior_trials(services, scenario, requester)
    record, _ = services.ledger.freeze(scenario.experiment, requester)
    saved = list(services.faults.rules)
    services.faults.rules.extend(FaultRule.parse(f) for f in scenario.faults)
    try:
        engine = primary_engine(services)
        run = await engine.start(record.experiment_id, requester)
    finally:
        services.faults.rules[:] = saved
    gate = None
    if run.current_step == "Research committee" and (run.status_reason or "").startswith("APPROVAL_REQUIRED"):
        gate = services.approvals.pending_gate(run.run_id)
        if scenario.decide if decide is None else decide:
            decision = (
                ApprovalDecision.APPROVE
                if gate.recommendation is ApprovalDecision.APPROVE
                else ApprovalDecision.REJECT
            )
            services.approvals.record(
                run_id=run.run_id,
                approver=DEMO_APPROVER,
                role="approver",
                decision=decision,
                reason=f"Demo decision following the gate ({gate.recommendation}): {' '.join(gate.reasons)}",
            )
            run = await engine.advance(run.run_id, DEMO_APPROVER)
    return ScenarioResult(
        scenario=scenario.name,
        run_id=run.run_id,
        status=str(run.status),
        current_step=run.current_step,
        decision=str(run.decision) if run.decision else None,
        gate=str(gate.recommendation) if gate else None,
        status_reason=run.status_reason,
        artifacts=artifact_hashes(services, run.run_id),
    )


async def record_demo(services: Services, names: list[str] | None = None) -> list[ScenarioResult]:
    chosen = [s for s in scenarios() if names is None or s.name in names]
    return [await run_scenario(services, s) for s in chosen]


@dataclass
class ReplayResult:
    original_run_id: str
    replay_run_id: str
    identical: bool
    compared: dict[str, tuple[str, str]]


async def replay_run(services: Services, run_id: str, actor: str = "replay") -> ReplayResult:
    """Re-execute a run's deterministic steps from its archived snapshot; compare artifact hashes."""
    original = services.repos.runs.get(run_id)
    if original is None:
        raise ConflictError(f"run {run_id} not found")
    record = services.ledger.get(original.experiment_id)
    acquisition = services.repos.steps.get(run_id, "Data acquisition")
    if acquisition is None or acquisition.artifact_evidence_id is None:
        raise ConflictError("the run has no archived data snapshot to replay from")
    snapshot_id = services.evidence.load_json(acquisition.artifact_evidence_id)["snapshot_evidence_id"]
    dataset = record.experiment.hypothesis.universe.dataset
    recorded = original.execution_manifest
    if recorded.get("format") != "rsf-execution/1":
        raise ConflictError(
            "this legacy run has no execution manifest; exact replay requires its archived configuration"
        )
    if recorded.get("runtime") != runtime_identity():
        raise ConflictError(
            "the archived run requires a different code/dependency/platform runtime; use its recorded release environment"
        )
    before = artifact_hashes(services, run_id, DETERMINISTIC_STEPS)
    replay_manifest = {**recorded, "snapshots": {dataset: snapshot_id}}
    steps = primary_steps()[: len(before)] if before else primary_steps()[:2]
    replay = await WorkflowEngine(services, steps, manifest=replay_manifest).start(
        record.experiment_id, actor, project_type="replay"
    )
    after = artifact_hashes(services, replay.run_id, DETERMINISTIC_STEPS)
    compared = {step: (before[step], after.get(step, "")) for step in before}
    return ReplayResult(run_id, replay.run_id, all(a == b for a, b in compared.values()), compared)


def platform_key() -> str:
    """Artifact hashes are exact only on the same platform (floating point can differ in the last bit)."""
    import platform

    import numpy

    return f"{platform.system()}-{platform.machine()}-py{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}-numpy{numpy.__version__}"


def manifest(results: list[ScenarioResult]) -> dict[str, Any]:
    """What a release archives: expected outcomes and artifact hashes for each scenario."""
    return {
        "format": "rsf-demo-manifest/2",
        "platform": platform_key(),
        "scenarios": {
            r.scenario: {
                "status": r.status,
                "current_step": r.current_step,
                "decision": r.decision,
                "gate": r.gate,
                "artifacts": r.artifacts,
            }
            for r in results
        },
    }
