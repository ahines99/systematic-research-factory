"""Canonical serialization and content-derived identifiers.

Every identifier that must be reproducible (experiment IDs, blob IDs, evidence IDs,
idempotency keys) is derived from a canonical byte encoding, never from randomness.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


def _default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetimes cannot be canonicalized")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"cannot canonicalize {type(value).__name__}")


def _check_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite floats must be encoded explicitly (use None)")
    if isinstance(value, dict):
        for v in value.values():
            _check_finite(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _check_finite(v)


def canonical_json(value: Any) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8, finite floats only."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    _check_finite(value)
    return json.dumps(
        value, default=_default, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any, length: int = 24) -> str:
    """A short, prefixed identifier derived from the canonical encoding of ``value``."""
    return f"{prefix}_{sha256_hex(canonical_json(value))[:length]}"
