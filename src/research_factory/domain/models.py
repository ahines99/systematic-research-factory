"""Cross-cutting contracts: evidence, findings, audit events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_require_aware)]
"""A timezone-aware datetime, normalized to UTC. Naive datetimes are rejected."""


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


class EvidenceRef(BaseModel):
    """A stored, immutable piece of evidence. ``content_hash`` addresses the blob."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    evidence_id: str
    source_uri: str
    source_type: str
    content_hash: str
    retrieved_at: UTCDateTime
    as_of: UTCDateTime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """A conclusion reached by a step, linked to the evidence that supports it."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    finding_id: str
    step: str
    finding_type: str
    title: str
    statement: str
    severity: Severity
    confidence: Confidence
    evidence_ids: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    """An append-only record of something that happened. Payloads are summarized, not raw."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = "1"
    event_id: int | None = None
    run_id: str | None
    step: str
    event_type: str
    actor: str
    created_at: UTCDateTime
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str = ""
