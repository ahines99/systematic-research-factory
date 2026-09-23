"""Append-only audit log (RSF-014) with payload redaction."""

from __future__ import annotations

from typing import Any

from ..domain.clock import Clock
from ..domain.identity import canonical_json, sha256_hex
from ..domain.models import AuditEvent
from ..persistence.repositories import AuditRepository

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
    "key_hash",
    "cookie",
)
MAX_INLINE_STRING = 2000


def redact(value: Any) -> Any:
    """Replace sensitive values and summarize large strings by hash, recursively."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if any(part in key.lower() for part in SENSITIVE_KEY_PARTS) and not key.lower().endswith(
                "_tokens"
            ):
                out[key] = "[REDACTED]"
            else:
                out[key] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str) and len(value) > MAX_INLINE_STRING:
        return {"sha256": sha256_hex(value.encode("utf-8")), "length": len(value)}
    if isinstance(value, float) and value != value:  # NaN
        return None
    return value


class AuditLog:
    def __init__(self, repo: AuditRepository, clock: Clock):
        self.repo = repo
        self.clock = clock

    def append(
        self,
        *,
        run_id: str | None,
        step: str,
        event_type: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        safe = redact(payload or {})
        event = AuditEvent(
            run_id=run_id,
            step=step,
            event_type=event_type,
            actor=actor,
            created_at=self.clock.now(),
            payload=safe,
            payload_hash=sha256_hex(canonical_json(safe)),
        )
        return self.repo.append(event)

    def events(self, run_id: str | None = None) -> list[AuditEvent]:
        return self.repo.list(run_id=run_id)
