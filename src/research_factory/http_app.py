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
from typing import Any, Literal

import anyio
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import text
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
MAX_REQUEST_BYTES = 4 * 1024 * 1024


class LiveRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Literal["clean-approved", "leak-caught", "overfit-rejected"] = "clean-approved"


class RequestBodyLimit:
    """Bound every HTTP request before a route parses it, including chunked bodies."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
                if length < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse(
                    {"error": {"code": "INVALID_INPUT", "message": "invalid Content-Length"}}, 400
                )(scope, receive, send)
                return
            if length > self.max_bytes:
                await self._reject(scope, receive, send)
                return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "request body exceeds 4 MiB"}}, 413
        )(scope, receive, send)


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
        if request.url.path in {"/healthz", "/readyz"}:
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
:root{{--bg:#f5f3ed;--fg:#18302f;--muted:#475d5b;--line:#b6c7c0;--card:#fff}}
body{{background:var(--bg);color:var(--fg);font:17px/1.6 system-ui,sans-serif;max-width:1060px;margin:0 auto;padding:32px 22px}}
h1{{font-size:clamp(2rem,5vw,3.7rem);line-height:1.08;max-width:850px;letter-spacing:-.04em}}
h2{{line-height:1.2}}a{{color:inherit;text-underline-offset:4px}}a:focus-visible{{outline:3px solid #b95015;outline-offset:5px}}
.runs{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px}}
.runs li{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:24px}}
.runs a{{font-size:1.2rem}}.runs .muted{{display:block;font-size:.85rem;margin:8px 0}}
.muted{{color:var(--muted)}}.label{{text-transform:uppercase;letter-spacing:.13em;font-size:.8rem;font-weight:700}}
.notice{{border-left:4px solid #ad4b17;padding:12px 18px;background:#fff6e9}}code{{font-size:.85em;overflow-wrap:anywhere}}
footer{{border-top:1px solid var(--line);margin-top:36px;padding-top:20px}}</style></head><body><main>{body}</main></body></html>"""
    )


def create_app(services: Services) -> Starlette:
    settings = services.settings
    keys = ApiKeyService(services.repos.api_keys, services.clock)
    mcp = create_server(services, local_principal=GUEST_PRINCIPAL)  # fail closed: unknown caller = guest

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok", "version": __version__})

    @mcp.custom_route("/readyz", methods=["GET"])
    async def readyz(_: Request) -> Response:
        """Read-only check of the database and a stored public-demo evidence blob."""

        def check() -> None:
            with services.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            runs = services.repos.runs.list(limit=20, requested_by=DEMO_REQUESTER)
            for run in runs:
                for step in services.repos.steps.list(run.run_id):
                    if step.step == "Data acquisition" and step.artifact_evidence_id:
                        acquisition = services.evidence.load_json(step.artifact_evidence_id)
                        services.evidence.load_bytes(acquisition["snapshot_evidence_id"])
                        return
            raise RuntimeError("public demo has not been seeded")

        try:
            with anyio.fail_after(5):
                await anyio.to_thread.run_sync(check, abandon_on_cancel=True)
        except Exception:
            return JSONResponse({"status": "not_ready", "version": __version__}, 503)
        return JSONResponse({"status": "ready", "version": __version__})

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
        body = (
            "<p class='label'>Systematic Research Factory · Research controls in action</p>"
            "<h1>A convincing backtest still has to earn approval.</h1>"
            "<p>Explore six recorded runs from hypothesis to evidence and decision. "
            "Start with the clean case, then compare a timing leak and repeated experimentation.</p>"
            "<p class='notice'><strong>Simulated prices. Scripted demonstration.</strong> "
            "Reviews use deterministic rules; approval actors are scripted to demonstrate role separation. "
            "These reports are not live-model evaluations, real human investment decisions or evidence of tradable alpha.</p>"
            "<h2>Inspect the evidence</h2>"
            f"<ul class='runs'>{''.join(items) or '<li>Recorded reports will appear here after the demo is seeded.</li>'}</ul>"
            "<footer><a href='https://github.com/ahines99/systematic-research-factory'>Source and reproduction instructions</a>"
            " · <a href='https://github.com/ahines99/systematic-research-factory/blob/main/docs/research/note.md'>"
            "Quantitative research study</a><p class='muted'>Research only. No trading or order-routing tools.</p></footer>"
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
            payload = LiveRunRequest.model_validate(await request.json())
        except (ValueError, ValidationError):
            return JSONResponse(
                {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"scenario must be one of {sorted(LIVE_SCENARIOS)}",
                    }
                },
                400,
            )
        name = payload.scenario
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
    app.add_middleware(RequestBodyLimit)
    return app
