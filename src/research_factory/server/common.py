"""Shared plumbing for every MCP tool: authentication, policy, audit, typed errors (RSF-029, RSF-030).

Tools are thin: they authenticate the caller, check the action against the policy table,
call a service, and return a Pydantic model. Errors come back as ``is_error`` results whose
text is JSON ``{"error": {"code", "message", "details"}}``; stack traces never leave the server.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from ..auth import GUEST, LOCAL_OPERATOR, ApiKeyService, Principal, bearer_token
from ..domain.errors import DomainError, ErrorCode, ForbiddenError, InvalidInputError
from ..domain.identity import canonical_json, sha256_hex
from ..domain.policies import require
from ..observability import bind, get_logger, unbind
from ..services.container import Services

log = get_logger(__name__)

DEMO_REQUESTERS = frozenset({"demo-researcher", "guest"})

# Set by the HTTP middleware for every request: the verified caller, or GUEST. MCP resource
# handlers do not receive request headers, so they rely on this.
HTTP_PRINCIPAL: ContextVar[Principal | None] = ContextVar("rsf_http_principal", default=None)


@dataclass
class ServerDeps:
    services: Services
    keys: ApiKeyService
    local_principal: Principal = LOCAL_OPERATOR
    tool_calls: list[str] = field(default_factory=list)


def error_payload(error: DomainError) -> str:
    return json.dumps({"error": error.to_dict()}, sort_keys=True)


def resolve_principal(deps: ServerDeps, ctx: Context[Any, Any] | None) -> Principal:
    """Who is calling. HTTP callers present an API key or are guests; local callers are the operator."""
    headers = None
    if ctx is not None:
        try:
            headers = ctx.headers
        except (LookupError, ValueError, AttributeError):
            headers = None
    if headers is None:
        from_http = HTTP_PRINCIPAL.get()
        return from_http if from_http is not None else deps.local_principal
    token = bearer_token(headers.get("authorization"))
    if token is None:
        return GUEST
    principal = deps.keys.verify(token)
    if principal is None:
        raise ForbiddenError("invalid or revoked API key")
    return principal


async def governed[T](
    deps: ServerDeps,
    ctx: Context[Any, Any] | None,
    tool: str,
    action: str,
    arguments: dict[str, Any],
    body: Callable[[Principal], Awaitable[T]],
) -> T:
    """Run one tool call under authentication, policy and audit."""
    deps.tool_calls.append(tool)
    audit = deps.services.audit
    principal: Principal | None = None
    bind(tool_name=tool)
    try:
        principal = resolve_principal(deps, ctx)
        require(action, principal)
        result = await body(principal)
        audit.append(
            run_id=None,
            step="mcp",
            event_type="tool_call",
            actor=principal.name,
            payload={
                "tool": tool,
                "role": str(principal.role),
                "arguments_sha256": _args_hash(arguments),
                "ok": True,
            },
        )
        return result
    except DomainError as exc:
        audit.append(
            run_id=None,
            step="mcp",
            event_type="tool_error",
            actor=principal.name if principal else "unauthenticated",
            payload={"tool": tool, "code": str(exc.code), "arguments_sha256": _args_hash(arguments)},
        )
        raise ToolError(error_payload(exc)) from None
    except ToolError:
        raise
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5])
        raise ToolError(error_payload(InvalidInputError(f"invalid input: {problems}"))) from None
    except Exception:
        log.exception("tool_crashed", tool=tool)
        raise ToolError(error_payload(DomainError("internal error", code=ErrorCode.INTERNAL))) from None
    finally:
        unbind("tool_name")


def _args_hash(arguments: dict[str, Any]) -> str:
    try:
        return sha256_hex(canonical_json(arguments))
    except (TypeError, ValueError):
        return sha256_hex(repr(sorted(arguments)).encode())
