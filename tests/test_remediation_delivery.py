"""Release guards, negative smoke behavior and replay of a preserved candidate archive."""

from __future__ import annotations

import hashlib
import json
import re
import runpy
import tarfile
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from research_factory.config import Settings
from research_factory.demo import artifact_hashes, replay_run
from research_factory.domain.errors import ConflictError
from research_factory.services.container import build_services
from research_factory.workflows.execution import runtime_identity

ROOT = Path(__file__).resolve().parents[1]
BASELINES = [ROOT / f"tests/fixtures/replay/candidate-linux-py{minor}.tar.gz" for minor in (312, 314)]


def test_release_guard_rejects_stale_reported_version(tmp_path: Path) -> None:
    check = runpy.run_path(str(ROOT / "scripts/check_release.py"))["check"]
    (tmp_path / "src/research_factory").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n')
    init = tmp_path / "src/research_factory/__init__.py"
    init.write_text('__version__ = "0.1.0"\n')
    with pytest.raises(SystemExit, match="must agree"):
        check("v1.0.0", tmp_path)
    init.write_text('__version__ = "1.0.0"\n')
    check("v1.0.0", tmp_path)
    with pytest.raises(SystemExit, match="must agree"):
        check("v1.0.0-extra", tmp_path)


def test_smoke_fails_when_only_liveness_works(monkeypatch: pytest.MonkeyPatch) -> None:
    check = runpy.run_path(str(ROOT / "scripts/smoke_deployment.py"))["check"]
    client_class = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok", "version": "0.1.0"})
        return httpx.Response(503, json={"status": "unavailable"})

    def client(**kwargs: Any) -> httpx.Client:
        return client_class(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "Client", client)
    with pytest.raises(httpx.HTTPStatusError, match="503"):
        check("http://testserver", expected_version="0.1.0")


@pytest.mark.anyio
@pytest.mark.parametrize("baseline", BASELINES, ids=lambda path: path.name)
async def test_preserved_baseline_replays_without_regenerating_expectations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, baseline: Path
) -> None:
    assert baseline.exists(), "the reviewed preserved baseline must be committed; tests never generate it"
    summary = json.loads(baseline.with_suffix(".json").read_text(encoding="utf-8"))
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == summary["archive_sha256"]
    with tarfile.open(baseline) as archive:
        archive.extractall(tmp_path, filter="data")
    archived = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    services = build_services(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'archive.db'}", blob_store=f"file://{tmp_path / 'blobs'}"
        )
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("historical replay must use archived data and must not call a provider")

    monkeypatch.setattr(services, "dataset", forbidden)
    monkeypatch.setattr(services.provider, "judge", forbidden)
    try:
        current = runtime_identity()
        # Current code must reject any incompatible historical runtime. A separate
        # required CI job selects the immutable historical source and actually replays it.
        if archived["runtime"] != current:
            run_id = next(iter(archived["scenarios"].values()))["run_id"]
            with pytest.raises(ConflictError, match="different code/dependency/platform"):
                await replay_run(services, run_id)
            return
        assert len(archived["scenarios"]) == 6
        for scenario in archived["scenarios"].values():
            assert artifact_hashes(services, scenario["run_id"], 6) == scenario["artifacts"]
            result = await replay_run(services, scenario["run_id"])
            assert result.identical
            assert {step: after for step, (_, after) in result.compared.items()} == scenario["artifacts"]
    finally:
        services.engine.dispose()


def test_release_deploys_the_scanned_digest_without_rebuilding() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert set(jobs["image"]["needs"]) == {"checks", "verify-version"}
    assert jobs["checks"]["uses"] == "./.github/workflows/ci.yml"
    deploy = jobs["deploy"]
    step = next(
        step
        for step in deploy["steps"]
        if step.get("name") == "copy and deploy the scanned digest (no rebuild)"
    )
    assert step["env"]["DIGEST"] == "${{ needs.image.outputs.digest }}"
    assert 'test "$copied" = "$DIGEST"' in step["run"]
    assert '--image "registry.fly.io/${app}@${DIGEST}"' in step["run"]
    assert "--remote-only" not in step["run"] and "docker build" not in step["run"]
    assert deploy["permissions"] == {"contents": "read", "packages": "read"}


def test_external_workflow_actions_are_immutable_and_postgres_runs_reservation_regression() -> None:
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        for action in re.findall(r"uses: ([^\s]+)", path.read_text(encoding="utf-8")):
            if not action.startswith("./"):
                assert re.fullmatch(r"[^@]+@[a-f0-9]{40}", action), (path.name, action)
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    commands = "\n".join(step.get("run", "") for step in ci["jobs"]["postgres"]["steps"])
    assert "tests/test_remediation_judgment.py" in commands
    assert "tests/test_remediation_workflow.py" in commands
