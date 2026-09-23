"""Structured logging (RSF-069).

JSON logs carry ``run_id``, ``step`` and ``tool_name`` via context variables. A redaction
processor removes secrets and summarizes large payloads before anything is written.
OpenTelemetry export is optional (RSF-070) and not required for v1.0 (ADR-0007).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_configured = False

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
MAX_INLINE = 2000


def _redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS) and not lowered.endswith("_tokens"):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(key, v) for v in value]
    if isinstance(value, str) and len(value) > MAX_INLINE:
        return f"[{len(value)} chars omitted]"
    return value


def redact_processor(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        if key == "event":
            continue
        event_dict[key] = _redact_value(key, event_dict[key])
    return event_dict


def configure_logging(level: str = "INFO", json: bool = True) -> None:
    global _configured
    logging.basicConfig(
        format="%(message)s", stream=sys.stderr, level=getattr(logging, level.upper(), logging.INFO)
    )
    renderer: Any = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_processor,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )
    _configured = True


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)


def bind(**values: Any) -> None:
    structlog.contextvars.bind_contextvars(**values)


def unbind(*keys: str) -> None:
    structlog.contextvars.unbind_contextvars(*keys)
