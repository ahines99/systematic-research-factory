"""Model-judgment contract (RSF-038).

A judgment step gets only structured artifacts and must return JSON matching this
contract. Output is rejected when it cites evidence the run does not have, states a fact
or calculation without evidence, or uses a verdict outside the step's allowed set.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..domain.models import Confidence

SCHEMA_VERSION = "judgment/1"


class ClaimKind(StrEnum):
    FACT = "fact"
    CALCULATION = "calculation"
    ASSUMPTION = "assumption"
    RISK = "risk"
    RECOMMENDATION = "recommendation"


CITATION_REQUIRED = {ClaimKind.FACT, ClaimKind.CALCULATION}


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ClaimKind
    statement: str = Field(min_length=5, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class JudgmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: str
    confidence: Confidence
    summary: str = Field(min_length=10, max_length=4000)
    claims: list[Claim] = Field(min_length=1, max_length=30)
    open_questions: list[str] = Field(default_factory=list, max_length=20)
    needs_evidence: bool = False


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
                    },
                    "required": ["kind", "statement", "evidence_ids"],
                    "additionalProperties": False,
                },
            },
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "needs_evidence": {"type": "boolean"},
        },
        "required": ["verdict", "confidence", "summary", "claims", "open_questions", "needs_evidence"],
        "additionalProperties": False,
    }


def validate_output(raw: Any, *, verdicts: list[str], allowed_evidence: set[str]) -> JudgmentOutput:
    try:
        output = JudgmentOutput.model_validate(raw)
    except ValidationError as exc:
        raise JudgmentValidationError([f"schema: {e['loc']}: {e['msg']}" for e in exc.errors()]) from exc
    problems: list[str] = []
    if output.verdict not in verdicts:
        problems.append(f"verdict {output.verdict!r} is not one of {verdicts}")
    for i, claim in enumerate(output.claims):
        unknown = [e for e in claim.evidence_ids if e not in allowed_evidence]
        if unknown:
            problems.append(f"claim {i} cites evidence that does not exist in this run: {unknown}")
        if claim.kind in CITATION_REQUIRED and not claim.evidence_ids:
            problems.append(
                f"claim {i} is a {claim.kind} without evidence; cite evidence or mark it an assumption"
            )
    if problems:
        raise JudgmentValidationError(problems)
    return output
