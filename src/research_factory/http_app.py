"""HTTP deployment (RSF-062, RSF-079; ADR-0004, ADR-0006).

* ``/mcp``: MCP over Streamable HTTP (stateless, so auto-stopped machines can serve any
  request). A bearer API key identifies the caller; a request with an *invalid* key is
  rejected with 401; a request with no key is a guest, limited by role and rate.
* ``/demo``: read-only pages for pre-recorded runs, open to anyone.
* ``/demo/live-run``: a small number of guest live runs per day, under the model-spend cap.
* ``/healthz``: liveness.

TLS terminates at the platform proxy.
"""

from __future__ import annotations

import html
import time
from collections import defaultdict, deque
from dataclasses import replace
from typing import Any

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from . import __version__
from .auth import GUEST as GUEST_PRINCIPAL
from .auth import ApiKeyService, bearer_token
from .demo import DEMO_REQUESTER, run_scenario, scenarios
from .domain.errors import BudgetExceededError, DomainError
from .judgment.providers import RulesProvider
from .report import build_run_report, render_html
from .server import create_server
from .server.common import HTTP_PRINCIPAL
from .services.budget import GUEST
from .services.container import Services

LIVE_SCENARIOS = {"clean-approved", "leak-caught", "overfit-rejected"}


class RateLimiter:
    """Sliding-window limiter per client key (IP for guests). Memory is bounded."""

    MAX_KEYS = 10_000

    def __init__(self, per_minute: int, clock: Any = time.monotonic):
        self.per_minute = per_minute
        self.clock = clock
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, now: float) -> None:
        for key in [k for k, w in self.hits.items() if not w or now - w[-1] > 60]:
            del self.hits[key]
        while len(self.hits) >= self.MAX_KEYS:  # still full of active keys: drop the oldest
            del self.hits[next(iter(self.hits))]

    def allow(self, key: str) -> bool:
        now = self.clock()
        if key not in self.hits and len(self.hits) >= self.MAX_KEYS:
            self._prune(now)
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return False
        window.append(now)
        return True


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: Any, keys: ApiKeyService, limiter: RateLimiter, trust_proxy_headers: bool = False
    ):
        super().__init__(app)
        self.keys = keys
        self.limiter = limiter
        self.trust_proxy_headers = trust_proxy_headers

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/healthz":
            return await call_next(request)
        token = bearer_token(request.headers.get("authorization"))
        if request.headers.get("authorization") and token is None:
            return JSONResponse(
                {"error": {"code": "FORBIDDEN", "message": "use 'Authorization: Bearer <key>'"}}, 401
            )
        if token is not None:
            principal = self.keys.verify(token)
            if principal is None:
                return JSONResponse(
                    {"error": {"code": "FORBIDDEN", "message": "invalid or revoked API key"}}, 401
                )
            return await self._with_principal(principal, request, call_next)
        forwarded = request.headers.get("fly-client-ip") if self.trust_proxy_headers else None
        client = forwarded or (request.client.host if request.client else "unknown")
        if not self.limiter.allow(client):
            return JSONResponse(
                {"error": {"code": "RATE_LIMITED", "message": "too many guest requests"}},
                429,
                headers={"Retry-After": "60"},
            )
        return await self._with_principal(GUEST_PRINCIPAL, request, call_next)

    @staticmethod
    async def _with_principal(
        principal: Any, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Tell the MCP layer who this request is from (resources get no headers of their own)."""
        token = HTTP_PRINCIPAL.set(principal)
        try:
            return await call_next(request)
        finally:
            HTTP_PRINCIPAL.reset(token)


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#5c5c5c;--line:#ddd}}@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#eee;--muted:#aaa;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px}}
a{{color:inherit}}li{{margin:10px 0}}.muted{{color:var(--muted)}}code{{font-size:13px}}</style></head><body>{body}</body></html>"""
    )


def create_app(services: Services) -> Starlette:
    settings = services.settings
    keys = ApiKeyService(services.repos.api_keys, services.clock)
    mcp = create_server(services, local_principal=GUEST_PRINCIPAL)  # fail closed: unknown caller = guest

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__})

    @mcp.custom_route("/demo", methods=["GET"])
    async def demo_index(_: Request) -> Response:
        runs = services.repos.runs.list(limit=200, requested_by=DEMO_REQUESTER)
        titles = {s.name: s for s in scenarios()}
        items = []
        for run in runs:
            record = services.ledger.get(run.experiment_id)
            hyp = record.experiment.hypothesis
            match = next(
                (s for s in titles.values() if s.experiment.hypothesis.hypothesis_id == hyp.hypothesis_id),
                None,
            )
            title = match.title if match else hyp.hypothesis_id
            story = match.story if match else hyp.statement
            items.append(
                f"<li><a href='/demo/runs/{html.escape(run.run_id)}'><strong>{html.escape(title)}</strong></a> "
                f"<span class='muted'>{html.escape(str(run.status))}{(' · ' + html.escape(str(run.decision))) if run.decision else ''}"
                f"</span><br>{html.escape(story)}</li>"
            )
        remaining = services.budget.guest_runs_remaining()
        body = (
            "<h1>Systematic Research Factory: recorded runs</h1>"
            "<p class='muted'>Governed, point-in-time research. Prices are simulated with planted effects (ADR-0003); "
            "nothing here says anything about real-world returns.</p>"
            f"<ul>{''.join(items) or '<li>No recorded runs yet. Run <code>rsf demo</code>.</li>'}</ul>"
            f"<p class='muted'>Live guest runs left today: {remaining}. POST /demo/live-run with "
            f'<code>{{"scenario": "clean-approved"}}</code>.</p>'
        )
        return _page("Recorded runs", body)

    @mcp.custom_route("/demo/runs/{run_id}", methods=["GET"])
    async def demo_run(request: Request) -> Response:
        run_id = request.path_params["run_id"]
        run = services.repos.runs.get(run_id)
        if run is None or run.requested_by not in (DEMO_REQUESTER, GUEST):
            return _page("Not found", "<h1>Run not found</h1>")
        return HTMLResponse(render_html(build_run_report(services, run_id)))

    @mcp.custom_route("/demo/live-run", methods=["POST"])
    async def live_run(request: Request) -> Response:
        try:
            body = await request.json()
        except ValueError:
            body = {}
        name = body.get("scenario", "clean-approved") if isinstance(body, dict) else "clean-approved"
        if name not in LIVE_SCENARIOS:
            return JSONResponse(
                {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"scenario must be one of {sorted(LIVE_SCENARIOS)}",
                    }
                },
                400,
            )
        try:
            services.budget.check_guest_run()
        except BudgetExceededError as exc:
            return JSONResponse({"error": exc.to_dict()}, 429)
        scenario = next(s for s in scenarios() if s.name == name)
        try:
            # Same path as the recorded demo (prior trials frozen first), reviewed by the free,
            # deterministic rules provider so guests never spend model budget.
            guest_services = replace(services, provider=RulesProvider())
            result = await run_scenario(guest_services, scenario, requester=GUEST, decide=False)
        except DomainError as exc:
            return JSONResponse({"error": exc.to_dict()}, 400)
        run = services.repos.runs.get(result.run_id)
        assert run is not None
        return JSONResponse(
            {
                "run_id": run.run_id,
                "status": str(run.status),
                "current_step": run.current_step,
                "reason": run.status_reason,
                "report": f"/demo/runs/{run.run_id}",
            }
        )

    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.http_allowed_hosts),
            allowed_origins=list(settings.http_allowed_origins),
        ),
    )
    app.add_middleware(
        ApiKeyMiddleware,
        keys=keys,
        limiter=RateLimiter(settings.guest_requests_per_minute),
        trust_proxy_headers=settings.trust_proxy_headers,
    )
    return app
