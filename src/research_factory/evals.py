"""Evaluation harness (RSF-010, RSF-032, RSF-033).

Golden cases are YAML files. Each case runs in a fresh, isolated store and is scored on
the seven dimensions from the specification:

1. tool_correctness        right capability, valid arguments, expected result or error code
2. evidence_fidelity       every cited evidence ID exists; facts and calculations are cited
3. calculation_fidelity    reported statistics match an independent recomputation
4. permission_fidelity     forbidden actions fail closed
5. uncertainty_calibration insufficient evidence becomes an explicit NEEDS_EVIDENCE outcome
6. recovery                injected failures produce controlled, audited behaviour
7. cost_latency            each case stays within its time and model-cost budget

Besides a case's own expectations, evidence and calculation fidelity are checked
automatically on every workflow case.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import yaml
from mcp import Client
from pydantic import BaseModel, ConfigDict, Field

from .auth import Principal, Role
from .config import Budgets, Settings
from .demo import demo_experiment
from .domain.errors import DomainError
from .domain.project_models import ApprovalDecision
from .judgment.providers import JudgmentProvider, ScriptedProvider, provider_from_settings
from .server import create_server
from .services.container import Services, build_services
from .workflows.faults import FaultInjector, FaultRule
from .workflows.primary import primary_engine

DIMENSIONS = (
    "tool_correctness",
    "evidence_fidelity",
    "calculation_fidelity",
    "permission_fidelity",
    "uncertainty_calibration",
    "recovery",
    "cost_latency",
)


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approver: str = "golden-approver"
    role: str = "approver"
    decision: str = "follow_gate"  # or approve | reject | needs_more_evidence
    expect_error: str | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    as_role: str = "researcher"
    as_user: str = "golden-researcher"
    expect_error: str | None = None
    expect: dict[str, Any] = Field(default_factory=dict)  # dotted path -> expected value


class Expect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_status: str | None = None
    current_step: str | None = None
    reason_prefix: str | None = None
    gate: str | None = None
    decision: str | None = None
    finding_types_include: list[str] = Field(default_factory=list)
    finding_types_exclude: list[str] = Field(default_factory=list)
    audit_events_include: list[str] = Field(default_factory=list)
    max_seconds: float = 60.0
    max_cost_usd: float = 0.50


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    kind: str = "workflow"  # workflow | mcp
    dimensions: list[str]
    adversarial: bool = False
    experiment: dict[str, Any] = Field(default_factory=dict)
    prior_trials: int = 0
    faults: list[str] = Field(default_factory=list)
    reviewer_script: list[Any] = Field(default_factory=list)
    budgets: dict[str, Any] = Field(default_factory=dict)
    approve: Approval | None = None
    calls: list[ToolCall] = Field(default_factory=list)
    expect: Expect = Field(default_factory=Expect)


def load_cases(path: Path) -> list[GoldenCase]:
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    return [GoldenCase.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))) for f in files]


class Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, dimension: str, name: str, passed: bool, detail: str = "") -> None:
        self.items.append({"dimension": dimension, "name": name, "passed": bool(passed), "detail": detail})


def _dig(obj: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj.get(part) if isinstance(obj, dict) else None
    return obj


# --------------------------------------------------------------------------- automatic checks


def check_evidence_fidelity(services: Services, run_id: str, checks: Checks) -> None:
    missing = []
    for f in services.repos.findings.list_for_run(run_id):
        missing += [e for e in f.evidence_ids if not services.evidence.exists(e)]
    uncited = []
    for result in services.repos.steps.list(run_id):
        if not result.artifact_evidence_id:
            continue
        doc = services.evidence.load_json(result.artifact_evidence_id)
        if doc.get("format") in ("rsf-judgment/1", "rsf-committee-decision/1"):
            for claim in doc["output"]["claims"]:
                missing += [e for e in claim["evidence_ids"] if not services.evidence.exists(e)]
                if claim["kind"] in ("fact", "calculation") and not claim["evidence_ids"]:
                    uncited.append(claim["statement"][:60])
    checks.add("evidence_fidelity", "cited evidence exists", not missing, ", ".join(missing[:3]))
    checks.add("evidence_fidelity", "facts and calculations are cited", not uncited, "; ".join(uncited[:3]))


def check_calculation_fidelity(services: Services, run_id: str, checks: Checks) -> None:
    steps = {s.step: s for s in services.repos.steps.list(run_id)}
    stats_step, bt_step = steps.get("Statistical review"), steps.get("Backtest")
    if stats_step and stats_step.artifact_evidence_id and bt_step and bt_step.artifact_evidence_id:
        stats = services.evidence.load_json(stats_step.artifact_evidence_id)
        net = np.array(services.evidence.load_json(bt_step.artifact_evidence_id)["net"])
        sd = float(net.std())
        sharpe = float(net.mean()) / sd * math.sqrt(252) if sd else 0.0
        checks.add(
            "calculation_fidelity",
            "Sharpe recomputed from daily returns",
            abs(sharpe - stats["sharpe_annualized"]) < 1e-9,
            f"{sharpe:.6f} vs {stats['sharpe_annualized']:.6f}",
        )
        # Independent deflated Sharpe from the report's own inputs.
        sr, n, skew, kurt = stats["sharpe_per_period"], stats["n_obs"], stats["skew"], stats["kurtosis"]
        trials, var = stats["n_trials"], stats["var_sr"]
        g = 0.5772156649015329
        nd = NormalDist()
        sr0 = (
            0.0
            if trials <= 1
            else math.sqrt(var)
            * ((1 - g) * nd.inv_cdf(1 - 1 / trials) + g * nd.inv_cdf(1 - 1 / (trials * math.e)))
        )
        dsr = nd.cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr**2))
        checks.add(
            "calculation_fidelity",
            "deflated Sharpe recomputed",
            abs(dsr - stats["deflated_sharpe"]) < 1e-9,
            f"{dsr:.6f} vs {stats['deflated_sharpe']:.6f}",
        )
    audit_step, feat_step = steps.get("Leakage audit"), steps.get("Feature build")
    if audit_step and audit_step.artifact_evidence_id and feat_step and feat_step.artifact_evidence_id:
        audit = services.evidence.load_json(audit_step.artifact_evidence_id)
        rows = services.evidence.load_json(feat_step.artifact_evidence_id)["lineage"]["rows"]
        future = any(
            datetime.fromisoformat(i["knowledge_ts"]) > datetime.fromisoformat(r["decision_ts"])
            for r in rows
            for i in r["inputs"]
        )
        claimed = next(c for c in audit["checks"] if c["check"] == "knowledge_time")
        checks.add(
            "calculation_fidelity",
            "knowledge-time verdict independently confirmed",
            claimed["passed"] == (not future),
            f"audit passed={claimed['passed']}, independent future inputs={future}",
        )


# --------------------------------------------------------------------------- runners


def _provider(case: GoldenCase, provider: str) -> JudgmentProvider:
    if case.reviewer_script:
        return ScriptedProvider(outputs=deque(case.reviewer_script))
    return provider_from_settings(
        provider, Settings().anthropic_model, None if provider == "rules" else _api_key()
    )


def _api_key() -> str | None:
    key = Settings().anthropic_api_key
    return key.get_secret_value() if key else None


def _services(case: GoldenCase, provider: str) -> Services:
    settings = Settings(
        database_url="sqlite://",
        blob_store="memory://",
        budgets=Budgets(**case.budgets),
        retry=Settings().retry.model_copy(update={"base_delay_seconds": 0.0}),
    )
    faults = FaultInjector([FaultRule.parse(f) for f in case.faults])
    return build_services(settings, provider=_provider(case, provider), faults=faults)


async def _run_workflow_case(case: GoldenCase, services: Services, checks: Checks) -> None:
    exp_kw = {"hypothesis_id": "golden", **case.experiment}
    family = exp_kw.get("family", "golden-family")
    for k in range(case.prior_trials):
        services.ledger.freeze(
            demo_experiment(
                f"prior-{k:03d}", family=family, dataset=exp_kw.get("dataset", "synthetic:v1"), delay=31 + k
            ),
            "golden-researcher",
        )
    record, _ = services.ledger.freeze(demo_experiment(**{**exp_kw, "family": family}), "golden-researcher")
    engine = primary_engine(services)
    run = await engine.start(record.experiment_id, "golden-researcher")
    gate = services.approvals.pending_gate(run.run_id)
    if case.approve is not None:
        decision = (
            gate.recommendation
            if case.approve.decision == "follow_gate"
            else ApprovalDecision(case.approve.decision)
        )
        try:
            services.approvals.record(
                run_id=run.run_id,
                approver=case.approve.approver,
                role=case.approve.role,
                decision=decision,
                reason="golden case decision",
            )
            error = None
            run = await engine.advance(run.run_id, case.approve.approver)
        except DomainError as exc:
            error = str(exc.code)
        if case.approve.expect_error:
            checks.add(
                "permission_fidelity",
                f"approval fails closed with {case.approve.expect_error}",
                error == case.approve.expect_error,
                f"got {error}",
            )
        else:
            checks.add("tool_correctness", "approval accepted", error is None, f"got {error}")

    e = case.expect
    findings = services.repos.findings.list_for_run(run.run_id)
    types = {f.finding_type for f in findings}
    dim = "tool_correctness"
    if e.run_status:
        checks.add(
            dim, "run status", str(run.status) == e.run_status, f"{run.status} (expected {e.run_status})"
        )
    if e.current_step:
        checks.add(dim, "stopping step", run.current_step == e.current_step, f"{run.current_step}")
    if e.reason_prefix:
        target = "uncertainty_calibration" if "NEEDS_EVIDENCE" in e.reason_prefix else "recovery"
        checks.add(
            target,
            "status reason",
            (run.status_reason or "").startswith(e.reason_prefix),
            f"{run.status_reason}",
        )
    if e.gate:
        target = "uncertainty_calibration" if e.gate == "needs_more_evidence" else dim
        checks.add(
            target,
            "gate recommendation",
            str(gate.recommendation) == e.gate,
            f"{gate.recommendation}: {gate.reasons}",
        )
    if e.decision:
        checks.add(dim, "final decision", str(run.decision) == e.decision, f"{run.decision}")
    for t in e.finding_types_include:
        target = "uncertainty_calibration" if t == "needs_evidence" else dim
        checks.add(target, f"finding {t} present", t in types, f"types={sorted(types)}")
    for t in e.finding_types_exclude:
        checks.add(dim, f"finding {t} absent", t not in types, f"types={sorted(types)}")
    events = {ev.event_type for ev in services.audit.events(run.run_id)}
    for ev_type in e.audit_events_include:
        checks.add("recovery", f"audit event {ev_type}", ev_type in events, "")
    check_evidence_fidelity(services, run.run_id, checks)
    check_calculation_fidelity(services, run.run_id, checks)


async def _run_mcp_case(case: GoldenCase, services: Services, checks: Checks) -> None:
    for call in case.calls:
        server = create_server(services, local_principal=Principal(call.as_user, Role(call.as_role)))
        async with Client(server) as client:
            result = await client.call_tool(call.tool, call.arguments)
        text = getattr(result.content[0], "text", "") if result.content else ""
        if call.expect_error:
            code = None
            if result.is_error:
                try:
                    code = json.loads(text[text.index("{") :])["error"]["code"]
                except (ValueError, KeyError):
                    code = "INVALID_INPUT"  # schema validation by the MCP layer (plain text)
            dim = "permission_fidelity" if call.expect_error == "FORBIDDEN" else "tool_correctness"
            checks.add(
                dim,
                f"{call.tool} fails with {call.expect_error}",
                code == call.expect_error,
                f"got {code}: {text[:120]}",
            )
        else:
            checks.add("tool_correctness", f"{call.tool} succeeds", not result.is_error, text[:120])
            for path, expected in call.expect.items():
                actual = _dig(result.structured_content, path)
                checks.add(
                    "tool_correctness",
                    f"{call.tool}.{path}",
                    actual == expected,
                    f"{actual!r} (expected {expected!r})",
                )


async def run_case(case: GoldenCase, provider: str = "rules") -> dict[str, Any]:
    services = _services(case, provider)
    checks = Checks()
    started = time.perf_counter()
    try:
        if case.kind == "mcp":
            await _run_mcp_case(case, services, checks)
        else:
            await _run_workflow_case(case, services, checks)
    except Exception as exc:  # a crash is a failed case, never a crashed suite
        checks.add("tool_correctness", "case ran without crashing", False, f"{type(exc).__name__}: {exc}")
    seconds = time.perf_counter() - started
    cost = services.repos.usage.cost_since(datetime(2000, 1, 1, tzinfo=UTC))
    checks.add("cost_latency", "within time budget", seconds <= case.expect.max_seconds, f"{seconds:.2f}s")
    checks.add("cost_latency", "within cost budget", cost <= case.expect.max_cost_usd, f"${cost:.4f}")
    return {
        "id": case.id,
        "title": case.title,
        "adversarial": case.adversarial,
        "dimensions": case.dimensions,
        "passed": all(c["passed"] for c in checks.items),
        "seconds": round(seconds, 3),
        "cost_usd": round(cost, 6),
        "checks": checks.items,
    }


async def run_eval_suite(path: Path, provider: str = "rules") -> dict[str, Any]:
    cases = load_cases(path)
    results = [await run_case(c, provider) for c in cases]
    dims: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in results:
        for c in r["checks"]:
            dims[c["dimension"]]["total"] += 1
            dims[c["dimension"]]["passed"] += int(c["passed"])
    return {
        "format": "rsf-scorecard/1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "provider": provider,
        "total": len(results),
        "passed": sum(r["passed"] for r in results),
        "adversarial": sum(r["adversarial"] for r in results),
        "dimensions": {d: dims[d] for d in DIMENSIONS},
        "cases": results,
    }


def write_scorecard(scorecard: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    lines = [
        f"# Evaluation scorecard ({scorecard['provider']})",
        "",
        f"{scorecard['passed']}/{scorecard['total']} cases passed ({scorecard['adversarial']} adversarial). "
        f"Generated {scorecard['generated_at']}.",
        "",
        "| Dimension | Checks passed |",
        "|---|---|",
        *[f"| {d} | {v['passed']}/{v['total']} |" for d, v in scorecard["dimensions"].items()],
        "",
        "| Case | Result | Seconds | Failed checks |",
        "|---|---|---|---|",
    ]
    for r in scorecard["cases"]:
        failed = "; ".join(f"{c['name']} ({c['detail']})" for c in r["checks"] if not c["passed"]) or "-"
        lines.append(f"| {r['id']} | {'pass' if r['passed'] else 'FAIL'} | {r['seconds']} | {failed} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
