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
import platform
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any, Literal

import numpy as np
import yaml
from mcp import Client
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Engine, select

from .auth import Principal, Role
from .config import Budgets, Settings
from .demo import demo_experiment
from .domain.clock import SystemClock
from .domain.errors import DomainError, InvalidInputError
from .domain.identity import canonical_json, sha256_hex
from .domain.project_models import ApprovalDecision
from .judgment import prompts
from .judgment.contract import JudgmentValidationError, output_schema, validate_output
from .judgment.providers import JudgmentProvider, JudgmentRequest, ScriptedProvider, provider_from_settings
from .persistence.budget import BudgetReservations
from .persistence.db import make_engine, upgrade
from .persistence.repositories import Repositories
from .persistence.schema import model_usage
from .server import create_server
from .services.budget import BudgetGuard
from .services.container import Services, build_services
from .workflows.engine import WorkflowEngine
from .workflows.execution import runtime_identity
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


class JudgmentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_slug: Literal["point_in_time_review", "full_red_team", "economic_rationale"] = "point_in_time_review"
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_documents: dict[str, Any] = Field(default_factory=dict)
    expect_verdict: str | None = None
    expect_rejected: bool = False
    injected_output: dict[str, Any] | None = None


class GoldenCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    kind: Literal["workflow", "mcp", "judgment"] = "workflow"
    dimensions: list[str] = Field(min_length=1)
    adversarial: bool = False
    experiment: dict[str, Any] = Field(default_factory=dict)
    prior_trials: int = 0
    faults: list[str] = Field(default_factory=list)
    reviewer_script: list[Any] = Field(default_factory=list)
    budgets: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)  # overrides of StatisticalThresholds
    approve: Approval | None = None
    calls: list[ToolCall] = Field(default_factory=list)
    expect: Expect = Field(default_factory=Expect)
    judgment: JudgmentTask = Field(default_factory=JudgmentTask)

    @field_validator("dimensions")
    @classmethod
    def valid_dimensions(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or set(value) - set(DIMENSIONS):
            raise ValueError("dimensions must be known and unique")
        return value


def load_cases(path: Path) -> list[GoldenCase]:
    files = sorted(path.glob("*.yaml")) if path.is_dir() else [path]
    try:
        cases = [GoldenCase.model_validate(yaml.safe_load(f.read_text(encoding="utf-8"))) for f in files]
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as exc:
        raise InvalidInputError(f"invalid evaluation case input: {exc}") from exc
    if not cases:
        raise InvalidInputError("evaluation suite must contain at least one case")
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        raise InvalidInputError("evaluation case IDs must be unique")
    return cases


class Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, dimension: str, name: str, passed: bool, detail: str = "") -> None:
        if dimension not in DIMENSIONS:
            raise ValueError(f"unknown evaluation dimension {dimension}")
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
            check_judgment_fidelity(services, run_id, doc, checks)
    checks.add("evidence_fidelity", "cited evidence exists", not missing, ", ".join(missing[:3]))
    checks.add("evidence_fidelity", "facts and calculations are cited", not uncited, "; ".join(uncited[:3]))


def check_judgment_fidelity(services: Services, run_id: str, doc: dict[str, Any], checks: Checks) -> None:
    """Revalidate archived raw output against cited artifact fields and its rendered output."""
    evidence = {
        ref.evidence_id: services.evidence.load_json(ref.evidence_id)
        for _, ref in services.repos.evidence.list_for_run(run_id)
        if ref.source_type.startswith("artifact:")
    }
    try:
        request = doc["request"]
        # Restrict to the exact catalog supplied at the time, not later run artifacts.
        allowed = {e["evidence_id"] for e in request["payload"]["evidence_catalog"]}
        validated = validate_output(
            doc["raw_output"],
            verdicts=request["verdicts"],
            allowed_evidence=allowed,
            evidence_documents=evidence,
            review_scope=request["payload"].get("review_scope", {}),
        )
        same = validated.model_dump(mode="json") == doc["output"]
        detail = "" if same else "stored rendered judgment differs from validated artifact-field rendering"
    except (KeyError, TypeError, JudgmentValidationError) as exc:
        same, detail = False, str(exc)
    checks.add("calculation_fidelity", "judgment numbers resolve to cited fields", same, detail)


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
    if case.kind == "judgment" and case.judgment.injected_output is not None:
        return ScriptedProvider(outputs=deque([case.judgment.injected_output]))
    if case.reviewer_script:
        return ScriptedProvider(outputs=deque(case.reviewer_script))
    return provider_from_settings(
        provider, Settings().anthropic_model, None if provider == "rules" else _api_key()
    )


def _api_key() -> str | None:
    key = Settings().anthropic_api_key
    return key.get_secret_value() if key else None


def _accounting_engine(url: str) -> Engine:
    engine = make_engine(url)
    if engine.dialect.name == "sqlite" and (
        not engine.url.database or engine.url.database == ":memory:" or "mode=memory" in str(engine.url)
    ):
        engine.dispose()
        raise InvalidInputError(
            "paid evaluations require a durable accounting database, not in-memory SQLite"
        )
    upgrade(engine)
    return engine


def _services(case: GoldenCase, provider: str, accounting_engine: Engine | None = None) -> Services:
    configured = Settings()
    budgets = Budgets(**case.budgets)
    selected_provider = _provider(case, provider)
    paid = selected_provider.name not in ("rules", "scripted")
    if accounting_engine is not None and paid:
        # Fixtures can reduce owner-authorized limits, never raise them for paid calls.
        budgets = Budgets.model_validate(
            {
                name: min(value, getattr(configured.budgets, name))
                for name, value in budgets.model_dump().items()
            }
        )
    settings = Settings(
        thresholds=type(Settings().thresholds).model_validate(
            {**Settings().thresholds.model_dump(), **case.thresholds}
        ),
        database_url="sqlite://",
        blob_store="memory://",
        budgets=budgets,
        retry=Settings().retry.model_copy(update={"base_delay_seconds": 0.0}),
    )
    faults = FaultInjector([FaultRule.parse(f) for f in case.faults])
    services = build_services(settings, provider=selected_provider, faults=faults)
    if accounting_engine is not None and paid:
        services.repos.usage = Repositories(accounting_engine).usage
        services.budget = BudgetGuard(
            budgets,
            services.repos.usage,
            services.repos.runs,
            SystemClock(),
            accounting_engine=accounting_engine,
        )
    return services


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
                except (ValueError, KeyError, TypeError):
                    code = None  # an unexpected/malformed error is never an expected typed failure
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


async def _run_judgment_case(case: GoldenCase, services: Services, checks: Checks) -> dict[str, Any]:
    """A paired, evidence-backed judgment task; same input and scorer in both Skill arms."""
    task = case.judgment
    record, _ = services.ledger.freeze(demo_experiment("judgment-evaluation"), "golden-researcher")
    run = WorkflowEngine(services, []).create_run(
        record.experiment_id, "golden-researcher", "evaluation:judgment"
    )
    refs = {
        name: services.evidence.record_json(
            doc,
            source_uri=f"golden://{case.id}/{name}",
            source_type="artifact:evaluation-input",
            run_id=run.run_id,
            step="Evaluation input",
        )
        for name, doc in task.evidence_documents.items()
    }

    def resolve(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("$evidence:"):
            return refs[value.removeprefix("$evidence:")].evidence_id
        if isinstance(value, dict):
            return {k: resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        return value

    if task.injected_output is not None:
        assert isinstance(services.provider, ScriptedProvider)
        services.provider.outputs = deque([resolve(task.injected_output)])
    payload = {
        **resolve(task.payload),
        "review_scope": prompts.review_scope(task.step_slug),
        "evidence_catalog": [
            {"evidence_id": ref.evidence_id, "source_type": ref.source_type, "step": "Evaluation input"}
            for ref in refs.values()
        ],
    }
    request = JudgmentRequest(
        task.step_slug,
        prompts.system_prompt(task.step_slug),
        payload,
        prompts.VERDICTS[task.step_slug],
        output_schema(prompts.VERDICTS[task.step_slug]),
    )
    # The same durable admission/accounting as production, even for standalone model tasks.
    import anyio

    response = await anyio.to_thread.run_sync(
        services.budget.invoke, services.provider, request, run.run_id, "Judgment evaluation", services.engine
    )
    error: str | None = None
    rendered: dict[str, Any] | None = None
    try:
        output = validate_output(
            response.raw,
            verdicts=request.verdicts,
            allowed_evidence={ref.evidence_id for ref in refs.values()},
            evidence_documents={ref.evidence_id: task.evidence_documents[name] for name, ref in refs.items()},
            review_scope=payload["review_scope"],
        )
        rendered = output.model_dump(mode="json")
    except JudgmentValidationError as exc:
        error = str(exc)
    checks.add(
        "evidence_fidelity",
        "judgment contract expected rejection",
        (error is not None) == task.expect_rejected,
        error or "accepted",
    )
    if not task.expect_rejected:
        checks.add(
            "uncertainty_calibration",
            "targeted review verdict",
            rendered is not None and rendered["verdict"] == task.expect_verdict,
            f"expected {task.expect_verdict}; got {rendered['verdict'] if rendered else error}",
        )
        checks.add(
            "uncertainty_calibration",
            "targeted review uncertainty flag",
            rendered is not None
            and rendered["needs_evidence"]
            == (task.expect_verdict in ("needs_evidence", "needs_more_evidence")),
            "missing assigned evidence must be explicit, and supported answers must not invent uncertainty",
        )
    else:
        checks.add(
            "calculation_fidelity",
            "fabrication cannot enter a reviewed artifact",
            error is not None,
            error or "fabrication accepted",
        )
    return {
        "step": task.step_slug,
        "provider": response.provider,
        "model": response.model,
        "prompt_version": prompts.prompt_version(task.step_slug),
        "skill_version": prompts.skill_version(task.step_slug),
        "schema_hash": prompts.schema_version(task.step_slug),
        "request": {
            "system": request.system,
            "payload": payload,
            "schema": request.schema,
            "verdicts": request.verdicts,
        },
        "raw_output": response.raw,
        "output": rendered,
        "validation_error": error,
        "input_hash": sha256_hex(canonical_json(payload)),
    }


async def run_case(
    case: GoldenCase, provider: str = "rules", accounting_engine: Engine | None = None
) -> dict[str, Any]:
    own_accounting = provider == "anthropic" and accounting_engine is None
    if own_accounting:
        accounting_engine = _accounting_engine(Settings().database_url)
    services = _services(case, provider, accounting_engine)
    checks = Checks()
    started = time.perf_counter()
    artifacts: list[dict[str, Any]] = []
    try:
        if case.kind == "mcp":
            await _run_mcp_case(case, services, checks)
        elif case.kind == "judgment":
            artifacts.append(await _run_judgment_case(case, services, checks))
        else:
            await _run_workflow_case(case, services, checks)
    except Exception as exc:  # a crash is a failed case, never a crashed suite
        checks.add("tool_correctness", "case ran without crashing", False, f"{type(exc).__name__}: {exc}")
    seconds = time.perf_counter() - started
    case_runs = services.repos.runs.list(limit=100)
    run_ids = {run.run_id for run in case_runs}
    cost = sum(services.repos.usage.totals_for_run(run_id)[1] for run_id in run_ids)
    checks.add("cost_latency", "within time budget", seconds <= case.expect.max_seconds, f"{seconds:.2f}s")
    checks.add("cost_latency", "within cost budget", cost <= case.expect.max_cost_usd, f"${cost:.4f}")
    inputs: dict[str, str] = {}
    audits: list[dict[str, Any]] = []
    for run in case_runs:
        audits.extend(e.payload for e in services.audit.events(run.run_id) if e.payload.get("model"))
        for _, ref in services.repos.evidence.list_for_run(run.run_id):
            inputs[ref.evidence_id] = ref.content_hash
            if ref.source_type.startswith("artifact:"):
                doc = services.evidence.load_json(ref.evidence_id)
                if doc.get("format") in ("rsf-judgment/1", "rsf-committee-decision/1"):
                    artifacts.append(doc)
    paid_accounting = accounting_engine is not None and services.provider.name not in ("rules", "scripted")
    usage_engine = accounting_engine if paid_accounting else services.engine
    assert usage_engine is not None
    with usage_engine.connect() as conn:
        usage = [
            dict(row)
            for row in conn.execute(select(model_usage).where(model_usage.c.run_id.in_(run_ids))).mappings()
        ]
    outstanding = (
        [row for row in BudgetReservations(accounting_engine).outstanding() if row["run_id"] in run_ids]
        if paid_accounting and accounting_engine is not None
        else []
    )
    provenance = {
        "requested_provider": provider,
        "configured_provider": services.provider.name,
        "actual_providers": sorted({a["provider"] for a in [*artifacts, *audits] if "provider" in a}),
        "actual_models": sorted({a["model"] for a in [*artifacts, *audits, *usage] if "model" in a}),
        "model_exercised": any(a.get("provider") == "anthropic" for a in [*artifacts, *audits])
        or (paid_accounting and bool(usage)),
        "skills_enabled": prompts.skills_enabled(),
        "case_sha256": sha256_hex(canonical_json(case)),
        "runtime": runtime_identity(),
        "python_full": platform.python_version(),
        "thresholds": services.settings.thresholds.model_dump(mode="json"),
        "budgets": services.settings.budgets.model_dump(mode="json"),
        "evidence_hashes": inputs,
        "judgments": artifacts,
        "judgment_audit": audits,
        "accounting": {
            "durable": paid_accounting,
            "ledger_id": sha256_hex(accounting_engine.url.render_as_string(hide_password=True).encode())
            if accounting_engine is not None
            else None,
            "run_ids": sorted(run_ids),
            "outstanding": json.loads(json.dumps(outstanding, default=str)),
            "settled_usage": json.loads(json.dumps(usage, default=str)),
        },
    }
    services.engine.dispose()
    if own_accounting and accounting_engine is not None:
        accounting_engine.dispose()
    return {
        "id": case.id,
        "title": case.title,
        "adversarial": case.adversarial,
        "dimensions": case.dimensions,
        "passed": all(c["passed"] for c in checks.items),
        "seconds": round(seconds, 3),
        "cost_usd": round(cost, 6),
        "checks": checks.items,
        "provenance": provenance,
    }


async def run_eval_suite(
    path: Path, provider: str = "rules", accounting_url: str | None = None
) -> dict[str, Any]:
    cases = load_cases(path)
    accounting = (
        _accounting_engine(accounting_url or Settings().database_url) if provider == "anthropic" else None
    )
    try:
        results = [await run_case(c, provider, accounting) for c in cases]
    finally:
        if accounting is not None:
            accounting.dispose()
    dims: dict[str, dict[str, int]] = defaultdict(lambda: {"passed": 0, "total": 0})
    for r in results:
        for c in r["checks"]:
            dims[c["dimension"]]["total"] += 1
            dims[c["dimension"]]["passed"] += int(c["passed"])
    return {
        "format": "rsf-scorecard/2",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "provider": provider,
        "skills_enabled": prompts.skills_enabled(),
        "scope": "full_dimensions" if all(dims[d]["total"] for d in DIMENSIONS) else "partial_dimensions",
        "uncovered_dimensions": [d for d in DIMENSIONS if not dims[d]["total"]],
        "model_exercised_cases": sum(r["provenance"]["model_exercised"] for r in results),
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
        f"Skills: {'enabled' if scorecard['skills_enabled'] else 'disabled'}. "
        f"Scope: {scorecard['scope']}. Live-model cases: {scorecard['model_exercised_cases']}.",
        "Scripted and deterministic cases are reported separately in each case's provenance; "
        "passing them is not evidence of live-model quality.",
        "",
        "| Dimension | Checks passed |",
        "|---|---|",
        *[f"| {d} | {v['passed']}/{v['total']} |" for d, v in scorecard["dimensions"].items()],
        "",
        "| Case | Result | Seconds | Actual model | Failed checks |",
        "|---|---|---|---|---|",
    ]
    for r in scorecard["cases"]:
        failed = "; ".join(f"{c['name']} ({c['detail']})" for c in r["checks"] if not c["passed"]) or "-"
        models = ", ".join(r["provenance"]["actual_models"]) or "none (deterministic/MCP)"
        lines.append(
            f"| {r['id']} | {'pass' if r['passed'] else 'FAIL'} | {r['seconds']} | {models} | {failed} |"
        )
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
