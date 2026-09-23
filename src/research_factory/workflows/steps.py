"""The nine steps of the primary research workflow.

Steps 1-6 are deterministic. Steps 7-9 are judgment steps: the model (or the rules
provider) sees only structured artifacts, and its output is validated before it is kept.
Every step returns structured data, never prose alone.
"""

from __future__ import annotations

from typing import Any, ClassVar

import anyio
import numpy as np

from ..data.pit import PointInTimeData
from ..data.registry import dataset_names
from ..data.world import filing_to_dict
from ..domain.errors import InvalidInputError, NeedsEvidenceError
from ..domain.identity import content_id
from ..domain.models import Confidence, Finding, Severity
from ..domain.project_models import ApprovalDecision, StepStatus
from ..judgment import prompts
from ..judgment.contract import SCHEMA_VERSION, JudgmentValidationError, output_schema, validate_output
from ..judgment.providers import JudgmentRequest
from ..research.backtest import run_backtest
from ..research.features import FeatureTable, build_features, get_feature, rebalance_sessions
from ..research.leakage import audit_leakage
from ..research.quality import check_dataset, corrupt, scan_untrusted_text, stale
from ..research.statistics import PERIODS_PER_YEAR, deflated_sharpe_at, statistical_review
from ..services.approvals import APPROVAL_REQUIRED, COMMITTEE_STEP, compute_gate
from .base import StepContext, StepOutcome


async def run_blocking(fn: Any, *args: Any) -> Any:
    """Run CPU- or IO-bound work in a thread that a step timeout can abandon (RSF-045)."""
    return await anyio.to_thread.run_sync(fn, *args, abandon_on_cancel=True)


def make_finding(
    ctx: StepContext,
    step: str,
    finding_type: str,
    title: str,
    statement: str,
    severity: Severity,
    evidence_ids: list[str] | tuple[str, ...] = (),
    *,
    confidence: Confidence = Confidence.HIGH,
    assumptions: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
) -> Finding:
    finding_id = content_id(
        "fnd",
        {
            "run_id": ctx.run.run_id,
            "step": step,
            "type": finding_type,
            "title": title,
            "statement": statement,
        },
    )
    return Finding(
        finding_id=finding_id,
        step=step,
        finding_type=finding_type,
        title=title,
        statement=statement,
        severity=severity,
        confidence=confidence,
        evidence_ids=tuple(evidence_ids),
        assumptions=assumptions,
        metadata=metadata or {},
    )


def untrusted(text: str) -> str:
    return f"<untrusted_data>{text}</untrusted_data>"


# ============================================================================ 1


class HypothesisFreezeStep:
    name = "Hypothesis freeze"
    slug = "hypothesis-freeze"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        rec = ctx.record
        exp = rec.experiment
        ctx.services.ledger.verify(rec.experiment_id, exp.model_dump(mode="json", exclude={"experiment_id"}))
        get_feature(exp.hypothesis.feature.name)
        if exp.hypothesis.universe.dataset not in dataset_names():
            raise InvalidInputError(f"unknown dataset {exp.hypothesis.universe.dataset!r}")
        findings = [
            make_finding(
                ctx,
                self.name,
                "experiment_frozen",
                "Experiment frozen",
                f"Experiment {rec.experiment_id} is trial {rec.trial_number} in research family "
                f"'{rec.research_family}'. Any change to it creates a new experiment and a new trial.",
                Severity.INFO,
            )
        ]
        flags = scan_untrusted_text(exp.hypothesis.statement + "\n" + exp.hypothesis.rationale)
        if flags:
            findings.append(
                make_finding(
                    ctx,
                    self.name,
                    "untrusted_text",
                    "Instruction-like text in the hypothesis",
                    "The hypothesis text contains instruction-like content. It is passed to reviewers only as "
                    "data and cannot change any decision.",
                    Severity.MEDIUM,
                    metadata={"patterns": flags},
                )
            )
        artifact = {
            "format": "rsf-frozen-hypothesis/1",
            "experiment_id": rec.experiment_id,
            "research_family": rec.research_family,
            "trial_number": rec.trial_number,
            "hypothesis": exp.hypothesis.model_dump(mode="json"),
            "backtest": exp.backtest.model_dump(mode="json"),
            "untrusted_text_flags": flags,
        }
        return StepOutcome(StepStatus.COMPLETED, artifact=artifact, findings=findings)


# ============================================================================ 2


class DataAcquisitionStep:
    name = "Data acquisition"
    slug = "data-acquisition"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        s = ctx.services
        spec = ctx.experiment.backtest
        name = ctx.experiment.hypothesis.universe.dataset
        pinned = s.pinned_snapshots.get(name)
        if pinned is not None:
            # Replay: read the archived snapshot, never live data (RSF-059, RSF-077).
            view = s.snapshot(pinned)
            dataset_id = view.dataset_id
        else:
            dataset = await run_blocking(s.dataset, name)
            if s.faults.should_corrupt("data_source"):
                dataset = corrupt(dataset)
            if s.faults.should_stale("data_source"):
                dataset = stale(dataset)
            view = PointInTimeData(dataset).view_as_of(spec.as_of)
            dataset_id = dataset.dataset_id
        snapshot = s.evidence.record_bytes(
            view.to_bytes(),
            source_uri=f"rsf://datasets/{dataset_id}",
            source_type="dataset_snapshot",
            as_of=spec.as_of,
            metadata={
                "dataset_id": dataset_id,
                "content_hash": view.content_hash,
                "prices_simulated": view.prices_simulated,
            },
            run_id=ctx.run.run_id,
            step=self.name,
        )
        filings = s.evidence.record_json(
            [filing_to_dict(f) for f in view.filings],
            source_uri=f"rsf://datasets/{dataset_id}/filings",
            source_type="filings",
            as_of=spec.as_of,
            metadata={"dataset_id": dataset_id, "count": len(view.filings)},
            run_id=ctx.run.run_id,
            step=self.name,
        )
        s._snapshots[snapshot.evidence_id] = view
        issues = check_dataset(view)
        findings = [
            make_finding(
                ctx,
                self.name,
                "needs_evidence" if issue.blocking else "data_quality",
                f"Data quality: {issue.check.replace('_', ' ')}",
                issue.statement,
                Severity.HIGH if issue.blocking else Severity.MEDIUM,
                [snapshot.evidence_id],
                metadata={"examples": issue.examples},
            )
            for issue in issues
        ]
        if view.prices_simulated:
            findings.append(
                make_finding(
                    ctx,
                    self.name,
                    "data_provenance",
                    "Prices are simulated",
                    "Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing "
                    "about real-world returns.",
                    Severity.INFO,
                    [snapshot.evidence_id],
                )
            )
        artifact = {
            "format": "rsf-data-acquisition/1",
            "dataset_id": dataset_id,
            "dataset_content_hash": view.content_hash,
            "snapshot_evidence_id": snapshot.evidence_id,
            "filings_evidence_id": filings.evidence_id,
            "as_of": spec.as_of.isoformat(),
            "sessions": len(view.trading_days),
            "first_session": str(view.trading_days[0]),
            "last_session": str(view.trading_days[-1]),
            "securities": len(view.security_ids),
            "filings": len(view.filings),
            "prices_simulated": view.prices_simulated,
            "quality": [i.to_dict() for i in issues],
        }
        blocking = [i for i in issues if i.blocking]
        if blocking:
            return StepOutcome(
                StepStatus.NEEDS_REVIEW,
                artifact=artifact,
                findings=findings,
                evidence_ids=[snapshot.evidence_id, filings.evidence_id],
                reason="the source data failed quality checks: " + ", ".join(i.check for i in blocking),
                reason_code="NEEDS_EVIDENCE",
            )
        return StepOutcome(
            StepStatus.COMPLETED,
            artifact=artifact,
            findings=findings,
            evidence_ids=[snapshot.evidence_id, filings.evidence_id],
        )


# ============================================================================ 3


class FeatureBuildStep:
    name = "Feature build"
    slug = "feature-build"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        acq = ctx.artifact(DataAcquisitionStep.name)
        view = ctx.services.snapshot(acq["snapshot_evidence_id"])
        hyp, spec = ctx.experiment.hypothesis, ctx.experiment.backtest
        definition = get_feature(hyp.feature.name)

        def build() -> FeatureTable:
            return build_features(
                view,
                feature=hyp.feature.name,
                timing_basis=hyp.feature.timing_basis,
                universe_mode=hyp.universe.mode,
                sessions=rebalance_sessions(view, spec.start, spec.end, spec.hold_days),
                filings_evidence_id=acq["filings_evidence_id"],
                prices_evidence_id=acq["snapshot_evidence_id"],
            )

        table = await run_blocking(build)
        eligible = int(table.universe.sum())
        valued = int(np.isfinite(table.values).sum())
        if valued == 0:
            raise NeedsEvidenceError(
                "the feature could not be computed for any security on any decision date"
            )
        coverage = valued / eligible if eligible else 0.0
        doc = table.to_document(view)
        doc["input_sources"] = sorted(definition.input_sources)
        doc["coverage"] = coverage
        findings = [
            make_finding(
                ctx,
                self.name,
                "feature_coverage",
                "Feature coverage",
                f"'{hyp.feature.name}' ({hyp.feature.timing_basis} timing) has values for {valued} of {eligible} "
                f"eligible security-dates ({coverage:.0%}) across {len(table.sessions)} decision dates.",
                Severity.INFO if coverage >= 0.5 else Severity.MEDIUM,
                [acq["snapshot_evidence_id"], acq["filings_evidence_id"]],
            )
        ]
        return StepOutcome(StepStatus.COMPLETED, artifact=doc, findings=findings)


# ============================================================================ 4


def _load_table(ctx: StepContext) -> tuple[Any, FeatureTable]:
    acq = ctx.artifact(DataAcquisitionStep.name)
    view = ctx.services.snapshot(acq["snapshot_evidence_id"])
    return view, FeatureTable.from_document(ctx.artifact(FeatureBuildStep.name), view)


class BacktestStep:
    name = "Backtest"
    slug = "backtest"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        view, table = _load_table(ctx)
        hyp, spec = ctx.experiment.hypothesis, ctx.experiment.backtest
        result = await run_blocking(lambda: run_backtest(view, table, spec, hyp.expected_sign))
        n = len(result.net)
        if n == 0:
            raise NeedsEvidenceError("the backtest produced no returns: too few decision dates or securities")
        net, gross = result.net, result.gross
        sd = float(net.std())
        sharpe_pp = float(net.mean()) / sd if sd > 0 else 0.0
        doc = result.to_document(view)
        names = [len(p["long"]) for p in result.positions]
        doc["summary"] = {
            "n_obs": n,
            "sharpe_annualized": sharpe_pp * float(np.sqrt(PERIODS_PER_YEAR)),
            "net_total_return": float(np.prod(1 + net) - 1),
            "gross_annual_return": float(gross.mean()) * PERIODS_PER_YEAR,
            "net_annual_return": float(net.mean()) * PERIODS_PER_YEAR,
            "names_per_side": int(np.median(names)) if names else 0,
            "rebalances": len(result.turnover),
        }
        ctx.services.ledger.record_result(ctx.record.experiment_id, sharpe_pp, n)
        acq = ctx.artifact(DataAcquisitionStep.name)
        findings = [
            make_finding(
                ctx,
                self.name,
                "backtest_summary",
                "Backtest completed",
                f"{n} daily observations, annualized Sharpe {doc['summary']['sharpe_annualized']:.2f} after "
                f"{spec.transaction_cost_bps:g} bps costs, execution {result.lag_sessions} session(s) after the decision.",
                Severity.INFO,
                [acq["snapshot_evidence_id"]],
            )
        ]
        return StepOutcome(StepStatus.COMPLETED, artifact=doc, findings=findings)


# ============================================================================ 5


class LeakageAuditStep:
    name = "Leakage audit"
    slug = "leakage-audit"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        s = ctx.services
        acq = ctx.artifact(DataAcquisitionStep.name)
        view = s.snapshot(acq["snapshot_evidence_id"])
        feature_doc = ctx.artifact(FeatureBuildStep.name)
        backtest_doc = ctx.artifact(BacktestStep.name)
        filings_doc = s.evidence.load_json(acq["filings_evidence_id"])
        report = audit_leakage(
            feature_doc=feature_doc,
            backtest_doc=backtest_doc,
            filings_doc=filings_doc,
            dataset=view,
            input_sources=frozenset(feature_doc["input_sources"]),
        )
        cited = [
            ctx.artifacts[FeatureBuildStep.name],
            ctx.artifacts[BacktestStep.name],
            acq["filings_evidence_id"],
        ]
        failed = [c for c in report.checks if not c.passed]
        findings = [
            make_finding(
                ctx,
                self.name,
                f"leakage_{c.check}",
                f"Leakage: {c.check.replace('_', ' ')}",
                c.statement,
                c.severity,
                cited,
                metadata={"violations": c.violations, "examples": c.examples},
            )
            for c in failed
        ]
        if not failed:
            findings.append(
                make_finding(
                    ctx,
                    self.name,
                    "leakage_clean",
                    "No leakage detected",
                    " ".join(c.statement for c in report.checks),
                    Severity.INFO,
                    cited,
                )
            )
        return StepOutcome(
            StepStatus.COMPLETED,
            artifact=report.to_document(),
            findings=findings,
            fail_run=report.blocking,
            reason="leakage audit found blocking issues: " + ", ".join(c.check for c in failed)
            if report.blocking
            else None,
            reason_code="LEAKAGE" if report.blocking else None,
        )


# ============================================================================ 6


class StatisticalReviewStep:
    name = "Statistical review"
    slug = "statistical-review"

    async def execute(self, ctx: StepContext) -> StepOutcome:
        s = ctx.services
        view, table = _load_table(ctx)
        hyp, spec = ctx.experiment.hypothesis, ctx.experiment.backtest
        bt = ctx.artifact(BacktestStep.name)
        net, gross = np.array(bt["net"]), np.array(bt["gross"])
        delayed = await run_blocking(
            lambda: run_backtest(view, table, spec, hyp.expected_sign, extra_lag_sessions=1)
        )
        n_trials, sharpes = s.ledger.trial_context(ctx.record.experiment_id)
        report = statistical_review(
            net,
            gross,
            hold_days=spec.hold_days,
            ic_values=[x["ic"] for x in bt["ic_by_decision"]],
            turnover=[x["turnover"] for x in bt["turnover"]],
            trial_sharpes=sharpes,
            n_trials=n_trials,
            thresholds=s.settings.thresholds,
            delay_net=delayed.net,
        )
        cited = [ctx.artifacts[BacktestStep.name]]
        findings = []
        too_short = any(c.name == "min_observations" and not c.passed for c in report.checks)
        for c in report.checks:
            if c.passed:
                continue
            if too_short and c.name != "min_observations":
                continue  # on too short a sample the other statistics are not evidence either way
            if c.name == "min_observations":
                findings.append(
                    make_finding(
                        ctx,
                        self.name,
                        "needs_evidence",
                        "Too few observations",
                        f"{int(c.value)} daily observations; at least {int(c.threshold)} are required.",
                        Severity.HIGH,
                        cited,
                    )
                )
            elif c.name == "delay_decay":
                findings.append(
                    make_finding(
                        ctx,
                        self.name,
                        "fragility",
                        "Fragile to execution delay",
                        f"One extra session of delay loses {c.value:.0%} of the Sharpe ratio "
                        f"(limit {c.threshold:.0%}).",
                        Severity.HIGH,
                        cited,
                    )
                )
            else:
                findings.append(
                    make_finding(
                        ctx,
                        self.name,
                        "statistical_threshold",
                        f"Failed: {c.name.replace('_', ' ')}",
                        f"{c.description}: {c.value:.3f} against a threshold of {c.threshold:.3f}.",
                        Severity.HIGH,
                        cited,
                        metadata={"check": c.name},
                    )
                )
        if report.passed:
            findings.append(
                make_finding(
                    ctx,
                    self.name,
                    "statistics_passed",
                    "All statistical thresholds met",
                    f"Annualized Sharpe {report.sharpe_annualized:.2f}, Newey-West t {report.newey_west_t:.2f}, "
                    f"deflated Sharpe {report.deflated_sharpe:.3f} over {report.n_trials} trial(s), bootstrap "
                    f"{report.bootstrap_confidence:.0%} CI [{report.bootstrap_ci[0]:.2f}, {report.bootstrap_ci[1]:.2f}].",
                    Severity.INFO,
                    cited,
                )
            )
        return StepOutcome(StepStatus.COMPLETED, artifact=report.to_document(), findings=findings)


# ============================================================================ 7-9


class JudgmentStep:
    """Shared machinery: budget check, provider call, validation with one retry, stamping."""

    name: str
    slug: str
    verdicts: ClassVar[list[str]]
    max_attempts = 2

    def payload(self, ctx: StepContext) -> dict[str, Any]:
        raise NotImplementedError

    def extra_problems(self, verdict: str, payload: dict[str, Any]) -> list[str]:
        """Step-specific rules on top of the shared contract."""
        return []

    def evidence_catalog(self, ctx: StepContext) -> list[dict[str, str]]:
        return [
            {"evidence_id": ref.evidence_id, "source_type": ref.source_type, "step": step}
            for step, ref in ctx.services.repos.evidence.list_for_run(ctx.run.run_id)
        ]

    async def judge(self, ctx: StepContext) -> tuple[dict[str, Any] | None, list[Finding], dict[str, Any]]:
        s = ctx.services
        catalog = self.evidence_catalog(ctx)
        allowed = {e["evidence_id"] for e in catalog}
        payload = {**self.payload(ctx), "evidence_catalog": catalog}
        request = JudgmentRequest(
            step_slug=self.slug.replace("-", "_"),
            system=prompts.system_prompt(self.slug.replace("-", "_")),
            payload=payload,
            verdicts=self.verdicts,
            schema=output_schema(self.verdicts),
        )
        stamp: dict[str, Any] = {
            "provider": s.provider.name,
            "model": s.provider.model,
            "prompt_version": prompts.prompt_version(request.step_slug),
            "skill_version": prompts.skill_version(request.step_slug),
            "schema_version": SCHEMA_VERSION,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        problems: list[str] = []
        for _ in range(self.max_attempts):
            s.budget.check(ctx.run.run_id)
            response = await run_blocking(s.provider.judge, request)
            s.budget.record(
                run_id=ctx.run.run_id,
                step=self.name,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=response.cost_usd,
            )
            stamp["model"] = response.model
            stamp["input_tokens"] += response.input_tokens
            stamp["output_tokens"] += response.output_tokens
            stamp["cost_usd"] += response.cost_usd
            try:
                output = validate_output(response.raw, verdicts=self.verdicts, allowed_evidence=allowed)
                extra = self.extra_problems(output.verdict, payload)
                if extra:
                    raise JudgmentValidationError(extra)
            except JudgmentValidationError as exc:
                problems = exc.problems
                request = request.with_feedback(problems)
                continue
            artifact = {
                "format": "rsf-judgment/1",
                "step": self.name,
                **stamp,
                "output": output.model_dump(mode="json"),
            }
            return artifact, [], stamp
        finding = make_finding(
            ctx,
            self.name,
            "needs_evidence",
            "Reviewer output rejected",
            "The reviewer's output was rejected after validation: " + "; ".join(problems[:5]),
            Severity.HIGH,
            confidence=Confidence.HIGH,
            metadata={"problems": problems},
        )
        return None, [finding], stamp

    def summary_finding(
        self, ctx: StepContext, artifact: dict[str, Any], severity: Severity, finding_type: str
    ) -> Finding:
        out = artifact["output"]
        cited = sorted({e for c in out["claims"] for e in c["evidence_ids"]})
        return make_finding(
            ctx,
            self.name,
            finding_type,
            f"{self.name}: {out['verdict']}",
            out["summary"],
            severity,
            cited,
            confidence=Confidence(out["confidence"]),
            assumptions=tuple(c["statement"] for c in out["claims"] if c["kind"] == "assumption"),
            metadata={"verdict": out["verdict"], "model": artifact["model"]},
        )


def _statistics_brief(ctx: StepContext) -> dict[str, Any]:
    st = ctx.artifact(StatisticalReviewStep.name)
    keys = (
        "n_obs",
        "sharpe_annualized",
        "newey_west_t",
        "deflated_sharpe",
        "n_trials",
        "bootstrap_ci",
        "ic_mean",
        "ic_ir",
        "turnover_mean",
        "cost_drag_annualized",
        "delay_decay",
        "passed",
        "skew",
        "kurtosis",
    )
    return {k: st[k] for k in keys}


def _hypothesis_brief(ctx: StepContext) -> dict[str, Any]:
    h = ctx.experiment.hypothesis
    return {
        "hypothesis_id": h.hypothesis_id,
        "statement": untrusted(h.statement),
        "rationale": untrusted(h.rationale),
        "feature": h.feature.name,
        "feature_description": get_feature(h.feature.name).description,
        "timing_basis": str(h.feature.timing_basis),
        "expected_sign": h.expected_sign,
        "horizon_days": h.horizon_days,
    }


class EconomicRationaleStep(JudgmentStep):
    name = "Economic rationale review"
    slug = "economic-rationale"
    verdicts: ClassVar[list[str]] = ["supported", "unsupported", "needs_evidence"]

    def payload(self, ctx: StepContext) -> dict[str, Any]:
        frozen = ctx.artifact(HypothesisFreezeStep.name)
        return {
            "hypothesis": {**_hypothesis_brief(ctx), "rationale_raw": ctx.experiment.hypothesis.rationale},
            "statistics": _statistics_brief(ctx),
            "untrusted_text_flags": frozen.get("untrusted_text_flags", []),
        }

    async def execute(self, ctx: StepContext) -> StepOutcome:
        artifact, findings, stamp = await self.judge(ctx)
        if artifact is None:
            return StepOutcome(
                StepStatus.NEEDS_REVIEW,
                findings=findings,
                reason="reviewer output rejected",
                reason_code="NEEDS_EVIDENCE",
                audit=stamp,
            )
        verdict = artifact["output"]["verdict"]
        severity, ftype = {
            "supported": (Severity.INFO, "judgment"),
            "unsupported": (Severity.HIGH, "judgment"),
            "needs_evidence": (Severity.MEDIUM, "needs_evidence"),
        }[verdict]
        return StepOutcome(
            StepStatus.COMPLETED,
            artifact=artifact,
            findings=[self.summary_finding(ctx, artifact, severity, ftype)],
            audit=stamp,
        )


class ImplementationReviewStep(JudgmentStep):
    name = "Implementation review"
    slug = "implementation-review"
    verdicts: ClassVar[list[str]] = ["feasible", "concerns", "infeasible"]

    def payload(self, ctx: StepContext) -> dict[str, Any]:
        bt = ctx.artifact(BacktestStep.name)
        spec = ctx.experiment.backtest
        return {
            "hypothesis": _hypothesis_brief(ctx),
            "statistics": _statistics_brief(ctx),
            "backtest_summary": {
                **bt["summary"],
                "transaction_cost_bps": spec.transaction_cost_bps,
                "execution_delay_minutes": spec.execution_delay_minutes,
                "hold_days": spec.hold_days,
                "quantile": spec.quantile,
            },
        }

    async def execute(self, ctx: StepContext) -> StepOutcome:
        artifact, findings, stamp = await self.judge(ctx)
        if artifact is None:
            return StepOutcome(
                StepStatus.NEEDS_REVIEW,
                findings=findings,
                reason="reviewer output rejected",
                reason_code="NEEDS_EVIDENCE",
                audit=stamp,
            )
        verdict = artifact["output"]["verdict"]
        severity = {"feasible": Severity.INFO, "concerns": Severity.MEDIUM, "infeasible": Severity.HIGH}[
            verdict
        ]
        return StepOutcome(
            StepStatus.COMPLETED,
            artifact=artifact,
            findings=[self.summary_finding(ctx, artifact, severity, "judgment")],
            audit=stamp,
        )


class ResearchCommitteeStep(JudgmentStep):
    """Deterministic gate + drafted memo, then a human decision (pauses until one exists)."""

    name = COMMITTEE_STEP
    slug = "research-committee"
    verdicts: ClassVar[list[str]] = ["approve", "reject", "needs_more_evidence"]

    PERMISSIVENESS: ClassVar[dict[str, int]] = {"reject": 0, "needs_more_evidence": 1, "approve": 2}

    def extra_problems(self, verdict: str, payload: dict[str, Any]) -> list[str]:
        gate = payload["gate"]["recommendation"]
        if self.PERMISSIVENESS[verdict] > self.PERMISSIVENESS[gate]:
            return [
                f"the memo recommends '{verdict}' but the gate recommends '{gate}'; a memo may not be more permissive"
            ]
        return []

    def review_time_check(self, ctx: StepContext) -> Finding | None:
        """Deflated Sharpe at today's trial count (ADR-0008). Gates on the honest, review-time N."""
        s = ctx.services
        stats = ctx.artifact(StatisticalReviewStep.name)
        n_review, detail = s.ledger.review_trial_count(ctx.record.experiment_id)
        n_freeze = int(stats["n_trials"])
        if n_review <= n_freeze or not stats.get("n_obs"):
            return None
        dsr = deflated_sharpe_at(stats, n_review)
        threshold = s.settings.thresholds.min_deflated_sharpe
        cited = [ctx.artifacts[StatisticalReviewStep.name]]
        if dsr >= threshold:
            return make_finding(
                ctx,
                self.name,
                "review_time_trials",
                "Deflated Sharpe holds at today's trial count",
                f"{n_review} related trials exist now ({detail}); at that count the deflated Sharpe is {dsr:.3f} "
                f"(threshold {threshold}). At freeze it was {stats['deflated_sharpe']:.3f} over {n_freeze}.",
                Severity.INFO,
                cited,
            )
        return make_finding(
            ctx,
            self.name,
            "statistical_threshold",
            "Failed: deflated sharpe at today's trial count",
            f"{n_review} related trials exist now ({detail}); at that count the deflated Sharpe is {dsr:.3f}, "
            f"below the threshold of {threshold}. At freeze it was {stats['deflated_sharpe']:.3f} over {n_freeze}.",
            Severity.HIGH,
            cited,
            metadata={"check": "deflated_sharpe_review_time", "n_trials": n_review},
        )

    def payload(self, ctx: StepContext) -> dict[str, Any]:
        findings = ctx.services.repos.findings.list_for_run(ctx.run.run_id)
        gate = compute_gate(findings)
        return {
            "hypothesis": _hypothesis_brief(ctx),
            "statistics": _statistics_brief(ctx),
            "gate": gate.to_dict(),
            "findings": [
                {
                    "step": f.step,
                    "title": f.title,
                    "statement": f.statement,
                    "severity": str(f.severity),
                    "finding_type": f.finding_type,
                    "evidence_ids": list(f.evidence_ids),
                }
                for f in findings
            ],
        }

    async def execute(self, ctx: StepContext) -> StepOutcome:
        s = ctx.services
        review = self.review_time_check(ctx)
        if review is not None:
            s.repos.findings.add(
                ctx.run.run_id, review, s.clock.now()
            )  # visible to the gate and the approver
        gate = compute_gate(s.repos.findings.list_for_run(ctx.run.run_id))
        previous = s.repos.steps.get(ctx.run.run_id, self.name)
        stamp: dict[str, Any] = {}
        if previous is not None and previous.artifact_evidence_id:
            memo_artifact = {
                **s.evidence.load_json(previous.artifact_evidence_id),  # reuse the drafted memo
                "gate": gate.to_dict(),
            }
        else:
            drafted, findings, stamp = await self.judge(ctx)
            if drafted is None:
                return StepOutcome(
                    StepStatus.NEEDS_REVIEW,
                    findings=findings,
                    reason="memo draft rejected",
                    reason_code="NEEDS_EVIDENCE",
                    audit=stamp,
                )
            memo_artifact = {**drafted, "gate": gate.to_dict()}
        approvals = [a for a in s.repos.approvals.list_for_run(ctx.run.run_id) if a.step == self.name]
        if not approvals:
            return StepOutcome(
                StepStatus.NEEDS_REVIEW,
                artifact=memo_artifact,
                findings=[review] if review else [],
                reason=f"awaiting a committee decision; the gate recommends {gate.recommendation}",
                reason_code=APPROVAL_REQUIRED,
                audit={**stamp, "gate": gate.to_dict()},
            )
        decision = approvals[-1]
        final = {
            **memo_artifact,
            "format": "rsf-committee-decision/1",
            "decision": str(decision.decision),
            "approval_id": decision.approval_id,
            "approver": decision.approver,
            "reason": decision.reason,
            "human_changed_recommendation": decision.decision != gate.recommendation,
        }
        severity = Severity.INFO if decision.decision is ApprovalDecision.APPROVE else Severity.MEDIUM
        finding = make_finding(
            ctx,
            self.name,
            "committee_decision",
            f"Committee decision: {decision.decision}",
            f"{decision.approver} recorded '{decision.decision}' (gate recommended '{gate.recommendation}'): "
            f"{decision.reason}",
            severity,
            [ctx.artifacts.get(StatisticalReviewStep.name, "")]
            if ctx.artifacts.get(StatisticalReviewStep.name)
            else [],
        )
        return StepOutcome(
            StepStatus.COMPLETED,
            artifact=final,
            findings=[finding, *([review] if review else [])],
            run_decision=str(decision.decision),
            audit={
                "decision": str(decision.decision),
                "human_changed_recommendation": final["human_changed_recommendation"],
            },
        )
