"""Model-judgment contract (RSF-038).

A judgment step gets only structured artifacts and must return JSON matching this
contract. Output is rejected when it cites evidence the run does not have, states a fact
or calculation without evidence, or uses a verdict outside the step's allowed set.
"""

from __future__ import annotations

import math
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.models import Confidence

SCHEMA_VERSION = "judgment/3"


class ClaimKind(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    ASSUMPTION = "assumption"
    RISK = "risk"
    RECOMMENDATION = "recommendation"


CITATION_REQUIRED = {ClaimKind.FACT, ClaimKind.CALCULATION}


class MetricReference(BaseModel):
    """A numeric value is selected by evidence and JSON Pointer, never supplied by the model."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str
    field_path: str = Field(pattern=r"^/")
    format: str = Field(default=".3f", pattern=r"^(?:\.[0-6][f%]|d)$")


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ClaimKind
    statement: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    metric_refs: list[MetricReference] = Field(default_factory=list, max_length=20)


ATTACKS = (
    "lookahead",
    "restatement",
    "survivorship",
    "data_snooping",
    "execution_delay",
    "cost_sensitivity",
    "concentration",
    "regime_dependence",
    "capacity",
    "crowding",
)


class Attack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    attack: str
    evidence_ids: list[str] = Field(default_factory=list)
    severity: Literal["low", "medium", "high", "blocking"]
    status: Literal["refuted", "unrefuted", "not_tested"]
    criterion: str = Field(min_length=5)
    observation: str = Field(min_length=5)
    evidence_request: str = ""


class Dissent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    author: str
    role: str
    position: Literal["approve", "reject", "needs_more_evidence"]
    argument: str
    evidence_ids: list[str] = Field(default_factory=list)
    resolution_criterion: str
    response: str
    status: Literal["open", "resolved_by_evidence", "noted_not_adopted"]


class JudgmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: str
    confidence: Confidence
    summary: str = Field(min_length=10, max_length=4000)
    claims: list[Claim] = Field(min_length=1, max_length=30)
    open_questions: list[str] = Field(default_factory=list, max_length=20)
    needs_evidence: bool = False
    attacks: list[Attack] = Field(default_factory=list, max_length=10)
    dissent: list[Dissent] = Field(default_factory=list, max_length=20)


class JudgmentValidationError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def output_schema(verdicts: list[str]) -> dict[str, Any]:
    """JSON Schema for structured outputs: every object closed, every field required."""
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": verdicts},
            "confidence": {"type": "string", "enum": [c.value for c in Confidence]},
            "summary": {"type": "string"},
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": [k.value for k in ClaimKind]},
                        "statement": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "metric_refs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "evidence_id": {"type": "string"},
                                    "field_path": {"type": "string"},
                                    "format": {
                                        "type": "string",
                                        "enum": ["d", *[f".{i}{f}" for i in range(7) for f in ("f", "%")]],
                                    },
                                },
                                "required": ["evidence_id", "field_path", "format"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["kind", "statement", "evidence_ids", "metric_refs"],
                    "additionalProperties": False,
                },
            },
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "needs_evidence": {"type": "boolean"},
            "attacks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "attack": {"type": "string", "enum": list(ATTACKS)},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "severity": {"type": "string", "enum": ["low", "medium", "high", "blocking"]},
                        "status": {"type": "string", "enum": ["refuted", "unrefuted", "not_tested"]},
                        "criterion": {"type": "string"},
                        "observation": {"type": "string"},
                        "evidence_request": {"type": "string"},
                    },
                    "required": [
                        "attack",
                        "evidence_ids",
                        "severity",
                        "status",
                        "criterion",
                        "observation",
                        "evidence_request",
                    ],
                    "additionalProperties": False,
                },
            },
            "dissent": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        **{
                            k: {"type": "string"}
                            for k in ("author", "role", "argument", "resolution_criterion", "response")
                        },
                        "position": {"type": "string", "enum": ["approve", "reject", "needs_more_evidence"]},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "status": {
                            "type": "string",
                            "enum": ["open", "resolved_by_evidence", "noted_not_adopted"],
                        },
                    },
                    "required": [
                        "author",
                        "role",
                        "position",
                        "argument",
                        "evidence_ids",
                        "resolution_criterion",
                        "response",
                        "status",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "verdict",
            "confidence",
            "summary",
            "claims",
            "open_questions",
            "needs_evidence",
            "attacks",
            "dissent",
        ],
        "additionalProperties": False,
    }


def resolve_metric(ref: MetricReference, evidence_documents: dict[str, Any]) -> str:
    """Resolve an artifact field and format it deterministically (RFC 6901 pointer)."""
    value = evidence_documents[ref.evidence_id]
    for part in ref.field_path.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list) and not re.fullmatch(r"0|[1-9][0-9]*", key):
            raise ValueError("array pointer must use a nonnegative canonical index")
        value = value[int(key)] if isinstance(value, list) else value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("metric field must be a finite number")
    expected = METRIC_FORMATS.get(ref.field_path, ".3f")
    if ref.format != expected:
        raise ValueError(f"metric uses canonical format {expected}")
    if ref.format == "d":
        if value != int(value):
            raise ValueError("integer formatting requires an integral field")
        value = int(value)
    return format(value, ref.format)


_METRIC_SLOT = re.compile(r"\{metric:(\d+)\}")
METRIC_LABELS = {
    "/ic_mean": "Mean information coefficient",
    "/turnover_mean": "Mean turnover per rebalance",
    "/cost_drag_annualized": "Annualized cost drag",
    "/sharpe_annualized": "Annualized Sharpe ratio",
    "/sharpe_per_period": "Sharpe ratio per period",
    "/n_obs": "Number of observations",
    "/n_trials": "Number of trials",
    "/deflated_sharpe": "Deflated Sharpe probability",
    "/newey_west_t": "Newey-West t statistic",
}
METRIC_FORMATS = {
    "/n_obs": "d",
    "/n_trials": "d",
    "/turnover_mean": ".2f",
    "/cost_drag_annualized": ".2%",
}


def validate_output(
    raw: Any,
    *,
    verdicts: list[str],
    allowed_evidence: set[str],
    evidence_documents: dict[str, Any] | None = None,
    review_scope: dict[str, Any] | None = None,
) -> JudgmentOutput:
    try:
        output = JudgmentOutput.model_validate(raw)
    except ValidationError as exc:
        raise JudgmentValidationError([f"schema: {e['loc']}: {e['msg']}" for e in exc.errors()]) from exc
    problems: list[str] = []
    rendered: list[Claim] = []
    # Free-form numeric assertions cannot be verified by citation membership. Keep
    # numbers in explicit field references and render them after validation.
    for label, prose in [("summary", output.summary), *[("open question", q) for q in output.open_questions]]:
        if any(c.isnumeric() for c in prose):
            problems.append(f"{label} contains an ungrounded number; put quantitative claims in metric_refs")
    if output.verdict not in verdicts:
        problems.append(f"verdict {output.verdict!r} is not one of {verdicts}")
    scope = review_scope or {}
    seen = [a.attack for a in output.attacks]
    if len(seen) != len(set(seen)) or any(a not in ATTACKS for a in seen):
        problems.append("attack names must be known and unique")
    if scope.get("mode") == "full_red_team" and set(seen) != set(ATTACKS):
        problems.append("full red-team review requires every attack, including untested attacks")
    for attack in output.attacks:
        if any(e not in allowed_evidence for e in attack.evidence_ids):
            problems.append(f"attack {attack.attack} cites unknown evidence")
        if attack.status != "not_tested" and not attack.evidence_ids:
            problems.append(f"tested attack {attack.attack} needs evidence")
        if attack.status == "not_tested" and not attack.evidence_request.strip():
            problems.append(f"untested attack {attack.attack} needs an actionable evidence request")
        if (
            attack.status == "not_tested"
            and attack.severity in ("high", "blocking")
            and not output.needs_evidence
        ):
            problems.append(f"untested material attack {attack.attack} requires needs_evidence")
        if attack.status == "unrefuted" and attack.severity == "blocking" and output.verdict != "reject":
            problems.append("unrefuted blocking attack requires rejection")
        if (
            attack.status == "unrefuted"
            and attack.severity == "high"
            and output.verdict not in ("reject", "needs_more_evidence")
        ):
            problems.append("unrefuted high attack requires rejection or more evidence")
        for prose in (attack.criterion, attack.observation, attack.evidence_request):
            if any(c.isnumeric() for c in prose):
                problems.append("attack numbers must be grounded through calculation claims, not prose")
    authoritative = scope.get("dissent", [])
    for dissent in output.dissent:
        if any(e not in allowed_evidence for e in dissent.evidence_ids):
            problems.append("dissent cites unknown evidence")
        if dissent.role != "model_reviewer" and not any(
            dissent.model_dump(mode="json") == d for d in authoritative
        ):
            problems.append("human/earlier dissent must be preserved verbatim from supplied records")
        if dissent.role == "model_reviewer" and any(
            c.isnumeric()
            for text in (dissent.argument, dissent.response, dissent.resolution_criterion)
            for c in text
        ):
            problems.append("model dissent numbers belong in grounded calculation claims")
    if any(d not in [entry.model_dump(mode="json") for entry in output.dissent] for d in authoritative):
        problems.append("supplied dissent must be preserved verbatim, never omitted")
    for i, claim in enumerate(output.claims):
        unknown = [e for e in claim.evidence_ids if e not in allowed_evidence]
        if unknown:
            problems.append(f"claim {i} cites evidence that does not exist in this run: {unknown}")
        if claim.kind in CITATION_REQUIRED and not claim.evidence_ids:
            problems.append(
                f"claim {i} is a {claim.kind} without evidence; cite evidence or mark it an assumption"
            )
        if claim.kind is ClaimKind.CALCULATION and not claim.metric_refs:
            problems.append(f"claim {i} calculation requires structured metric_refs")
        if any(c.isnumeric() for c in _METRIC_SLOT.sub("", claim.statement)):
            problems.append(f"claim {i} contains an ungrounded number; use {{metric:index}} and metric_refs")
        slots = [int(x) for x in _METRIC_SLOT.findall(claim.statement)]
        if set(slots) != set(range(len(claim.metric_refs))):
            problems.append(f"claim {i} must use every metric reference through its matching placeholder")
        if claim.metric_refs and _METRIC_SLOT.sub("", claim.statement).strip(" ;,.\n"):
            problems.append(
                f"claim {i} quantitative statement must contain only metric placeholders; metric labels are rendered by code"
            )
        statement = claim.statement
        for j, ref in enumerate(claim.metric_refs):
            if ref.evidence_id not in allowed_evidence or ref.evidence_id not in claim.evidence_ids:
                problems.append(f"claim {i} metric reference must cite evidence that exists in this run")
                continue
            try:
                value = resolve_metric(ref, evidence_documents or {})
            except (KeyError, IndexError, TypeError, ValueError, OverflowError):
                problems.append(
                    f"claim {i} metric reference {j} does not resolve to a valid numeric artifact field"
                )
                continue
            label = METRIC_LABELS.get(ref.field_path, "Artifact field")
            statement = statement.replace(f"{{metric:{j}}}", f"{label} ({ref.field_path}): {value}")
        rendered.append(claim.model_copy(update={"statement": statement}))
    if problems:
        raise JudgmentValidationError(problems)
    return output.model_copy(update={"claims": rendered})


def render_memo(output: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    """Present the fixed memo sections without inventing content the reviewer omitted."""
    groups = {kind.value: [c for c in output["claims"] if c["kind"] == kind.value] for kind in ClaimKind}
    return {
        "scope": scope,
        "facts": groups["fact"],
        "calculations": groups["calculation"],
        "assumptions": groups["assumption"],
        "risks_and_counterarguments": groups["risk"],
        "recommendation": {"verdict": output["verdict"], "claims": groups["recommendation"]},
        "open_questions": output["open_questions"],
        "attacks": output.get("attacks", []),
        "dissent": output.get("dissent", []),
        "decision_record": None,
        "prices_simulated_notice": "Prices are simulated; no claim about real-world performance.",
    }
