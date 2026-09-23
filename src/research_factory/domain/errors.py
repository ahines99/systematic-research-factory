"""Typed domain errors. Every error that can reach a client carries a stable code."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    AS_OF_REQUIRED = "AS_OF_REQUIRED"
    HYPOTHESIS_FROZEN = "HYPOTHESIS_FROZEN"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CONFLICT = "CONFLICT"
    TIMEOUT = "TIMEOUT"
    INTERNAL = "INTERNAL"


class DomainError(Exception):
    """Base class for expected, client-safe failures."""

    code: ErrorCode = ErrorCode.INVALID_INPUT
    retryable: bool = False

    def __init__(self, message: str, *, code: ErrorCode | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": str(self.code), "message": self.message, "details": self.details}


class InvalidInputError(DomainError):
    code = ErrorCode.INVALID_INPUT


class AsOfRequiredError(DomainError):
    code = ErrorCode.AS_OF_REQUIRED


class HypothesisFrozenError(DomainError):
    code = ErrorCode.HYPOTHESIS_FROZEN


class NeedsEvidenceError(DomainError):
    code = ErrorCode.NEEDS_EVIDENCE


class ApprovalRequiredError(DomainError):
    code = ErrorCode.APPROVAL_REQUIRED


class ForbiddenError(DomainError):
    code = ErrorCode.FORBIDDEN


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT


class BudgetExceededError(DomainError):
    code = ErrorCode.BUDGET_EXCEEDED


class TransientError(DomainError):
    """A failure worth retrying: timeouts, rate limits, brief outages."""

    code = ErrorCode.UPSTREAM_UNAVAILABLE
    retryable = True


class StepTimeoutError(TransientError):
    code = ErrorCode.TIMEOUT


class UpstreamUnavailableError(TransientError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE
