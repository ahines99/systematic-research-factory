"""RSF-024, RSF-032, RSF-033, RSF-048, RSF-049, RSF-059, RSF-077, RSF-082."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import anyio
import pytest

from research_factory.cli import main
from research_factory.demo import manifest, record_demo, replay_run
from research_factory.evals import GoldenCase, load_cases, run_case, run_eval_suite, write_scorecard
from research_factory.report import build_run_report, render_html, render_markdown
from research_factory.services.container import Services

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evals" / "demo_manifest.json"


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> tuple[Services, list]:  # type: ignore[type-arg]
    from research_factory.config import Settings
    from research_factory.services.container import build_services

    services = build_services(Settings(database_url="sqlite://", blob_store="memory://"))
    return services, anyio.run(record_demo, services)


def test_demo_scenarios_reach_their_designed_outcomes(demo) -> None:  # type: ignore[no-untyped-def]
    _, results = demo
    outcome = {r.scenario: (r.status, r.current_step, r.decision) for r in results}
    assert outcome["clean-approved"] == ("complete", "Research committee", "approve")
    assert outcome["leak-caught"][:2] == ("failed", "Leakage audit")
    assert outcome["survivorship-caught"][:2] == ("failed", "Leakage audit")
    assert outcome["overfit-rejected"] == ("complete", "Research committee", "reject")
    assert outcome["fault-survived"] == ("complete", "Research committee", "approve")
    assert outcome["real-filings"][0] == "complete"


def test_demo_outcomes_match_the_committed_manifest(demo) -> None:  # type: ignore[no-untyped-def]
    """Outcomes are compared everywhere; byte-identity is proven by the replay test below.

    Artifact hashes are platform-sensitive in the last floating-point bit, so the committed
    manifest's hashes are informational outside the platform that produced them.
    """
    _, results = demo
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]
    current = manifest(results)["scenarios"]
    for name, expected in committed.items():
        for key in ("status", "current_step", "decision", "gate"):
            assert current[name][key] == expected[key], (name, key)


def test_replay_from_archived_snapshot_is_byte_identical(demo) -> None:  # type: ignore[no-untyped-def]
    services, results = demo
    for r in results:
        if r.scenario in ("clean-approved", "real-filings", "leak-caught"):
            replay = anyio.run(replay_run, services, r.run_id)
            assert replay.identical, (r.scenario, replay.compared)
            assert replay.compared


def test_replay_ignores_live_data_changes(demo, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    services, results = demo

    def broken(_: str) -> None:
        raise AssertionError("replay must not read live data")

    monkeypatch.setattr(services, "dataset", broken)
    replay = anyio.run(replay_run, services, results[0].run_id)
    assert replay.identical


def test_reports_render(demo) -> None:  # type: ignore[no-untyped-def]
    services, results = demo
    report = build_run_report(services, results[0].run_id)
    md, html = render_markdown(report), render_html(report)
    assert "## Findings" in md and "Prices are simulated" in md
    assert "<script" not in html and "prefers-color-scheme:dark" in html
    assert report["approvals"][0]["decision"] == "approve"
    assert report["statistics"]["passed"] is True


def test_html_report_escapes_untrusted_text(services: Services) -> None:
    from .conftest import make_experiment

    record, _ = services.ledger.freeze(
        make_experiment(statement="<script>alert('x')</script> earnings drift after filings"), "a"
    )
    run = anyio.run(
        __import__("research_factory.workflows.primary", fromlist=["x"]).primary_engine(services).start,
        record.experiment_id,
        "a",
    )
    html = render_html(build_run_report(services, run.run_id))
    assert "<script>alert" not in html and "&lt;script&gt;" in html


# ----------------------------------------------------------------------- CLI


def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = f"sqlite:///{tmp_path / 'cli.db'}"
    exp = ROOT / "examples" / "experiments" / "earnings_drift.yaml"
    assert main(["--database-url", db, "run", "--file", str(exp), "--requested-by", "alice"]) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["status"] == "needs_review"
    assert (
        main(
            [
                "--database-url",
                db,
                "approve",
                run["run_id"],
                "--decision",
                "approve",
                "--reason",
                "clean",
                "--approver",
                "bob",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    out = tmp_path / "report.md"
    assert main(["--database-url", db, "show", run["run_id"], "--out", str(out)]) == 0
    assert "Committee decision" in out.read_text(encoding="utf-8")
    lineage = tmp_path / "lineage.json"
    assert main(["--database-url", db, "lineage", run["run_id"], "--out", str(lineage)]) == 0
    assert main(["--database-url", db, "replay", run["run_id"]]) == 0
    assert (
        main(
            [
                "--database-url",
                db,
                "approve",
                run["run_id"],
                "--decision",
                "approve",
                "--reason",
                "x",
                "--approver",
                "bob",
            ]
        )
        == 2
    )


def test_cli_leak_example_fails_and_keys_work(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = f"sqlite:///{tmp_path / 'cli.db'}"
    leak = ROOT / "examples" / "experiments" / "earnings_drift_period_end_leak.yaml"
    assert main(["--database-url", db, "run", "--file", str(leak)]) == 3
    assert main(["--database-url", db, "keys", "create", "--owner", "bob", "--role", "approver"]) == 0
    out = capsys.readouterr().out
    assert "rsf_" in out
    assert main(["--database-url", db, "keys", "list"]) == 0
    assert "bob" in capsys.readouterr().out


def test_skill_script_accepts_exported_lineage(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The point-in-time Skill's script runs on real exported lineage (RSF-034)."""
    db = f"sqlite:///{tmp_path / 'cli.db'}"
    script = ROOT / "skills" / "point-in-time-research" / "scripts" / "check_pit_timestamps.py"
    for name, expected in (("earnings_drift.yaml", 0), ("earnings_drift_restated_leak.yaml", 1)):
        main(["--database-url", db, "run", "--file", str(ROOT / "examples" / "experiments" / name)])
        run_id = json.loads(capsys.readouterr().out)["run_id"]
        lineage = tmp_path / f"{name}.json"
        main(["--database-url", db, "lineage", run_id, "--out", str(lineage)])
        capsys.readouterr()
        proc = subprocess.run(
            [sys.executable, str(script), str(lineage)], capture_output=True, text=True, check=False
        )
        assert proc.returncode == expected, proc.stdout + proc.stderr


# ----------------------------------------------------------------------- evals


def test_golden_suite_has_25_plus_cases_with_adversarial_coverage() -> None:
    cases = load_cases(ROOT / "evals" / "golden")
    assert len(cases) >= 25
    assert len({c.id for c in cases}) == len(cases)
    adversarial = {c.id for c in cases if c.adversarial}
    # The spec's adversarial categories: prompt injection, stale data, duplicate entities,
    # contradictory evidence, missing required fields.
    for needed in (
        "20-prompt-injection",
        "19-stale-prices",
        "18-malformed-duplicates",
        "22-contradictory-reviewer",
        "28-mcp-missing-fields-and-roles",
    ):
        assert needed in adversarial
    dims = {d for c in cases for d in c.dimensions}
    assert dims == {
        "tool_correctness",
        "evidence_fidelity",
        "calculation_fidelity",
        "permission_fidelity",
        "uncertainty_calibration",
        "recovery",
        "cost_latency",
    }


def test_golden_suite_passes(tmp_path: Path) -> None:
    scorecard = anyio.run(run_eval_suite, ROOT / "evals" / "golden", "rules")
    write_scorecard(scorecard, tmp_path / "scorecard.json")
    failed = [c["id"] for c in scorecard["cases"] if not c["passed"]]
    assert not failed, failed
    assert (tmp_path / "scorecard.md").exists()


def test_harness_detects_a_wrong_expectation() -> None:
    case = GoldenCase(
        id="x",
        title="wrong",
        dimensions=["tool_correctness"],
        experiment={"timing": "period_end"},
        expect={"run_status": "complete"},
    )
    result = anyio.run(run_case, case, "rules")
    assert not result["passed"]


def test_cli_eval_accepts_provider_after_subcommand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "a.yaml").write_text(
        (ROOT / "evals" / "golden" / "06-same-close-execution.yaml").read_text(encoding="utf-8")
    )
    assert (
        main(["eval", "--provider", "rules", "--cases", str(cases), "--out", str(tmp_path / "s.json")]) == 0
    )
    assert "1/1 cases passed" in capsys.readouterr().out
