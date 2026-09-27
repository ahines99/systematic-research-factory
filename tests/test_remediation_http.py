"""Public request boundaries and deployment readiness from the September audit."""

from __future__ import annotations

from typing import Any

import anyio
import pytest
from starlette.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from research_factory.config import Settings
from research_factory.demo import DEMO_REQUESTER, demo_experiment
from research_factory.http_app import MAX_REQUEST_BYTES, RequestBodyLimit, create_app
from research_factory.services.container import Services, build_services
from research_factory.workflows.engine import WorkflowEngine
from research_factory.workflows.primary import primary_steps


@pytest.fixture
def services() -> Services:
    return build_services(
        Settings(database_url="sqlite://", blob_store="memory://", http_allowed_hosts=("testserver",))
    )


@pytest.mark.parametrize("payload", [{"scenario": []}, {"scenario": {}}, {"scenario": None}, [], None, 3])
def test_invalid_live_run_shapes_do_not_create_runs(services: Services, payload: Any) -> None:
    with TestClient(create_app(services)) as client:
        response = client.post("/demo/live-run", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"
    assert services.repos.runs.list() == []


def test_malformed_json_does_not_default_to_starting_a_run(services: Services) -> None:
    with TestClient(create_app(services)) as client:
        response = client.post(
            "/demo/live-run", content=b"{bad json", headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 400
    assert services.repos.runs.list() == []


@pytest.mark.parametrize("path", ["/demo/live-run", "/mcp"])
def test_all_http_routes_reject_oversize_bodies(services: Services, path: str) -> None:
    with TestClient(create_app(services)) as client:
        response = client.post(path, content=b"x" * (MAX_REQUEST_BYTES + 1))
    assert response.status_code == 413
    assert services.repos.runs.list() == []


@pytest.mark.parametrize("declared", [None, b"2"])
def test_chunked_and_underdeclared_bodies_stop_before_parsing(declared: bytes | None) -> None:
    messages: list[Message] = []
    calls = 0

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        pytest.fail("oversized request reached the application")

    async def receive() -> Message:
        nonlocal calls
        calls += 1
        assert calls <= 2, "middleware continued consuming an oversized stream"
        return {"type": "http.request", "body": b"x" * 6, "more_body": True}

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {"type": "http", "headers": [] if declared is None else [(b"content-length", declared)]}
    anyio.run(RequestBodyLimit(app, max_bytes=10), scope, receive, send)
    assert messages[0]["status"] == 413
    assert calls == 2


def _seed_readiness(services: Services) -> None:
    experiment = demo_experiment("readiness-check")
    record, _ = services.ledger.freeze(experiment, DEMO_REQUESTER)
    anyio.run(WorkflowEngine(services, primary_steps()[:2]).start, record.experiment_id, DEMO_REQUESTER)


def test_readiness_checks_real_seeded_evidence(services: Services, monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(create_app(services)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        _seed_readiness(services)
        assert client.get("/readyz").json()["status"] == "ready"

        def unavailable(_: str) -> bytes:
            raise OSError("private storage endpoint or credential must not leak")

        monkeypatch.setattr(services.blobs, "get", unavailable)
        response = client.get("/readyz")
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get("/healthz").status_code == 200


def test_readiness_detects_database_unavailability(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_readiness(services)

    def unavailable() -> None:
        raise OSError("database is unavailable")

    monkeypatch.setattr(services.engine, "connect", unavailable)
    with TestClient(create_app(services)) as client:
        assert client.get("/readyz").status_code == 503


def test_readiness_probes_do_not_exhaust_guest_request_quota(services: Services) -> None:
    _seed_readiness(services)
    with TestClient(create_app(services)) as client:
        for _ in range(services.settings.guest_requests_per_minute + 1):
            assert client.get("/readyz").status_code == 200
        assert client.get("/demo").status_code == 200
