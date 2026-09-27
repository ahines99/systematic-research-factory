"""A15/A16/A19: observable skill integration and fail-closed evaluation regressions."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from research_factory.cli import main
from research_factory.domain.errors import InvalidInputError
from research_factory.evals import (
    Checks,
    GoldenCase,
    check_judgment_fidelity,
    load_cases,
    run_case,
)
from research_factory.judgment import prompts
from research_factory.judgment.contract import (
    ATTACKS,
    JudgmentValidationError,
    render_memo,
    validate_output,
)
from research_factory.judgment.providers import AnthropicProvider
from research_factory.report import build_run_report, render_markdown
from research_factory.services.container import Services
from research_factory.workflows.primary import primary_engine

from .conftest import make_experiment

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def restore_skills() -> Any:
    before = prompts.skills_enabled()
    yield
    prompts.set_skills_enabled(before)


def test_empty_duplicate_and_invalid_case_configuration_fails(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="at least one"):
        load_cases(tmp_path)
    for update in (
        {"kind": "typo"},
        {"dimensions": ["invented"]},
        {"dimensions": []},
        {"dimensions": ["recovery", "recovery"]},
    ):
        with pytest.raises(ValidationError):
            GoldenCase.model_validate({"id": "test", "title": "test", "dimensions": ["recovery"], **update})
    for name in ("one", "two"):
        (tmp_path / f"{name}.yaml").write_text("id: duplicate\ntitle: test\ndimensions: [recovery]\n")
    with pytest.raises(InvalidInputError, match="unique"):
        load_cases(tmp_path)


def test_empty_cli_suite_returns_error(tmp_path: Path) -> None:
    assert main(["eval", "--provider", "rules", "--cases", str(tmp_path)]) == 2


@pytest.mark.anyio
async def test_unexpected_mcp_error_does_not_pass_as_invalid_input(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenClient:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def call_tool(self, *args: Any) -> Any:
            return SimpleNamespace(is_error=True, content=[SimpleNamespace(text="INTERNAL DATABASE FAILURE")])

    monkeypatch.setattr("research_factory.evals.Client", BrokenClient)
    case = GoldenCase(
        id="unexpected",
        title="unexpected",
        kind="mcp",
        dimensions=["tool_correctness"],
        calls=[{"tool": "healthcheck", "expect_error": "INVALID_INPUT"}],
    )
    result = await run_case(case)
    assert not result["passed"]
    assert "got None" in result["checks"][0]["detail"]


@pytest.mark.anyio
async def test_real_schema_failure_is_typed_without_error_masking() -> None:
    case = load_cases(ROOT / "evals/golden/28-mcp-missing-fields-and-roles.yaml")[0]
    result = await run_case(case)
    assert result["passed"], result["checks"]


def test_full_prompt_and_reference_mutations_change_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skill = tmp_path / "point-in-time-research"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("Procedure.")
    reference = skill / "references/timing.md"
    reference.write_text("Acceptance is the knowledge timestamp.")
    monkeypatch.setattr(prompts, "skills_root", lambda: tmp_path)
    prompts.set_skills_enabled(True)
    initial = prompts.prompt_version("point_in_time_review")
    skill_initial = prompts.skill_version("point_in_time_review")
    reference.write_text("Amendments have their own acceptance timestamp.")
    assert prompts.prompt_version("point_in_time_review") != initial
    assert prompts.skill_version("point_in_time_review") != skill_initial
    initial = prompts.prompt_version("point_in_time_review")
    monkeypatch.setattr(prompts, "NO_TOOLS_PREFACE", prompts.NO_TOOLS_PREFACE + " Changed instruction.")
    assert prompts.prompt_version("point_in_time_review") != initial
    schema = prompts.schema_version("point_in_time_review")
    original_schema = prompts.output_schema
    monkeypatch.setattr(
        prompts, "output_schema", lambda v: {**original_schema(v), "description": "new schema"}
    )
    assert prompts.schema_version("point_in_time_review") != schema


@pytest.mark.anyio
async def test_pit_pair_has_same_input_and_scorer_with_explicit_treatment() -> None:
    case = load_cases(ROOT / "evals/golden/31-pit-after-close.yaml")[0]
    results = []
    for enabled in (True, False):
        prompts.set_skills_enabled(enabled)
        results.append(await run_case(case))
    assert all(r["passed"] for r in results)
    treated, control = [r["provenance"]["judgments"][0] for r in results]
    assert treated["input_hash"] == control["input_hash"]
    assert treated["prompt_version"] != control["prompt_version"]
    assert "edgar-timestamps.md" in treated["request"]["system"]
    assert "edgar-timestamps.md" not in control["request"]["system"]
    assert treated["raw_output"] == control["raw_output"]  # rules do not read prompts
    assert all(not r["provenance"]["model_exercised"] for r in results)
    assert results[0]["provenance"]["actual_providers"] == ["rules"]


def test_default_cli_outputs_preserve_both_arms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    case = ROOT / "evals/golden/34-pit-clean-version.yaml"
    assert main(["eval", "--provider", "rules", "--cases", str(case)]) == 0
    assert main(["eval", "--provider", "rules", "--cases", str(case), "--no-skills"]) == 0
    treated = json.loads((tmp_path / "var/scorecard-rules-skills.json").read_text())
    control = json.loads((tmp_path / "var/scorecard-rules-no-skills.json").read_text())
    assert treated["skills_enabled"] and not control["skills_enabled"]
    assert treated["scope"] == "partial_dimensions"
    assert treated["cases"][0]["provenance"]["runtime"]["source_sha256"]


def _qualitative() -> dict[str, Any]:
    return {
        "verdict": "needs_more_evidence",
        "confidence": "low",
        "summary": "The assigned evidence is incomplete.",
        "claims": [{"kind": "risk", "statement": "Unverified checks remain.", "evidence_ids": []}],
        "open_questions": [],
        "needs_evidence": True,
        "attacks": [],
        "dissent": [],
    }


def test_full_red_team_keeps_missing_material_evidence_blocking() -> None:
    scope = prompts.review_scope("full_red_team")
    raw = _qualitative()
    with pytest.raises(JudgmentValidationError, match="every attack"):
        validate_output(raw, verdicts=["needs_more_evidence"], allowed_evidence=set(), review_scope=scope)
    raw["attacks"] = [
        {
            "attack": name,
            "evidence_ids": [],
            "severity": "high",
            "status": "not_tested",
            "criterion": "Registered criterion remains untested.",
            "observation": "Evidence was not supplied.",
            "evidence_request": "Research lead must register the missing analysis evidence.",
        }
        for name in ATTACKS
    ]
    valid = validate_output(raw, verdicts=["needs_more_evidence"], allowed_evidence=set(), review_scope=scope)
    assert len(valid.attacks) == 10
    raw["needs_evidence"] = False
    with pytest.raises(JudgmentValidationError, match="requires needs_evidence"):
        validate_output(raw, verdicts=["needs_more_evidence"], allowed_evidence=set(), review_scope=scope)


def test_supplied_dissent_is_preserved_and_not_impersonated() -> None:
    dissent = {
        "author": "reviewer42",
        "role": "human",
        "position": "reject",
        "argument": "Evidence ev_42 contradicts the assertion.",
        "evidence_ids": ["ev_42"],
        "resolution_criterion": "Resolve the contradictory evidence.",
        "response": "Unresolved.",
        "status": "open",
    }
    scope = {**prompts.review_scope("research_committee"), "dissent": [dissent]}
    raw = _qualitative()
    with pytest.raises(JudgmentValidationError, match="never omitted"):
        validate_output(raw, verdicts=["needs_more_evidence"], allowed_evidence={"ev_42"}, review_scope=scope)
    raw["dissent"] = [dissent]
    valid = validate_output(
        raw, verdicts=["needs_more_evidence"], allowed_evidence={"ev_42"}, review_scope=scope
    )
    memo = render_memo(valid.model_dump(mode="json"), scope)
    assert memo["dissent"] == [dissent] and memo["decision_record"] is None
    raw["dissent"] = [{**dissent, "argument": "Changed the human position."}]
    with pytest.raises(JudgmentValidationError, match="verbatim"):
        validate_output(raw, verdicts=["needs_more_evidence"], allowed_evidence={"ev_42"}, review_scope=scope)


@pytest.mark.anyio
async def test_stored_judgment_fidelity_detects_tampered_number_and_scoped_memo(services: Services) -> None:
    record, _ = services.ledger.freeze(make_experiment(), "alice")
    run = await primary_engine(services).start(record.experiment_id, "alice")
    step = services.repos.steps.get(run.run_id, "Economic rationale review")
    assert step and step.artifact_evidence_id
    doc = services.evidence.load_json(step.artifact_evidence_id)
    checks = Checks()
    check_judgment_fidelity(services, run.run_id, doc, checks)
    assert checks.items[0]["passed"]
    altered = copy.deepcopy(doc)
    altered["output"]["claims"][0]["statement"] = "Annualized Sharpe ratio: 999.0"
    check_judgment_fidelity(services, run.run_id, altered, checks)
    assert not checks.items[-1]["passed"]
    payload = doc["request"]["payload"]
    assert "rationale_raw" not in payload["hypothesis"]
    assert set(payload) == {
        "hypothesis",
        "statistics",
        "untrusted_text_flags",
        "evidence_catalog",
        "review_scope",
    }
    assert "bootstrap_method" in payload["statistics"]
    assert "full_red_team_signoff" in doc["memo"]["scope"]["excluded"]


def test_checker_bad_encoding_and_bad_json_have_machine_readable_exit_two(tmp_path: Path) -> None:
    script = ROOT / "skills/point-in-time-research/scripts/check_pit_timestamps.py"
    for blob in (b"\xff\xfe", b"{not json", b"[]"):
        path = tmp_path / "bad.json"
        path.write_bytes(blob)
        proc = subprocess.run(
            [sys.executable, str(script), "--json", str(path)], capture_output=True, text=True
        )
        assert proc.returncode == 2
        assert "error" in json.loads(proc.stdout)
        assert "Traceback" not in proc.stderr
        piped = subprocess.run(
            [sys.executable, "-X", "utf8", str(script), "--json", "-"], input=blob, capture_output=True
        )
        assert piped.returncode == 2 and "error" in json.loads(piped.stdout)
        assert b"Traceback" not in piped.stderr


@pytest.mark.anyio
async def test_prior_reviewer_dissent_survives_committee_and_report(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    dissent = {
        "author": "economic_reviewer",
        "role": "model_reviewer",
        "position": "needs_more_evidence",
        "argument": "The mechanism remains disputed despite the measured sign.",
        "evidence_ids": [],
        "resolution_criterion": "Supply independent mechanism evidence.",
        "response": "Not resolved.",
        "status": "open",
    }
    original = services.provider.judge

    def judge(request: Any) -> Any:
        response = original(request)
        if request.step_slug == "economic_rationale":
            return replace(response, raw={**response.raw, "dissent": [dissent]})
        return response

    monkeypatch.setattr(services.provider, "judge", judge)
    record, _ = services.ledger.freeze(make_experiment(), "alice")
    run = await primary_engine(services).start(record.experiment_id, "alice")
    step = services.repos.steps.get(run.run_id, "Research committee")
    assert step and step.artifact_evidence_id
    artifact = services.evidence.load_json(step.artifact_evidence_id)
    assert artifact["output"]["dissent"] == [dissent]
    assert artifact["memo"]["dissent"] == [dissent]
    scope = artifact["request"]["payload"]["review_scope"]
    assert scope["dissent_sources"][0]["artifact_evidence_id"]
    assert artifact["request"]["payload"]["prior_reviews"][0]["output"]["dissent"] == [dissent]
    assert dissent["argument"] in render_markdown(build_run_report(services, run.run_id))


@pytest.mark.anyio
async def test_paid_eval_uses_durable_owner_limits_across_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fake Anthropic transport only: no key, HTTP request or actual token generation."""
    monkeypatch.setenv("RSF_DATABASE_URL", f"sqlite:///{tmp_path / 'owner-accounting.db'}")
    monkeypatch.setenv("RSF_BUDGETS__MAX_COST_USD_PER_DAY", "0.25")
    monkeypatch.setenv("RSF_BUDGETS__MAX_COST_USD_PER_RUN", "0.25")
    calls = []

    def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        payload = json.loads(kwargs["messages"][0]["content"].split("\n\n", 1)[1])
        raw = {
            "verdict": "clean",
            "confidence": "high",
            "summary": "The original value was accepted before the decision.",
            "claims": [
                {
                    "kind": "fact",
                    "statement": "The cited original was available at the decision.",
                    "evidence_ids": [payload["evidence_catalog"][0]["evidence_id"]],
                    "metric_refs": [],
                }
            ],
            "open_questions": [],
            "needs_evidence": False,
            "attacks": [],
            "dissent": [],
        }
        return SimpleNamespace(
            model="claude-fable-5-1",
            usage=SimpleNamespace(input_tokens=100, output_tokens=kwargs["max_tokens"]),
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(raw))],
        )

    client = SimpleNamespace(
        beta=SimpleNamespace(
            messages=SimpleNamespace(
                create=create, count_tokens=lambda **kw: SimpleNamespace(input_tokens=100)
            )
        )
    )
    monkeypatch.setattr(
        "research_factory.evals._provider",
        lambda case, provider: AnthropicProvider(model="claude-fable-5-1", client=client),
    )
    case = load_cases(ROOT / "evals/golden/34-pit-clean-version.yaml")[0].model_copy(
        update={"budgets": {"max_cost_usd_per_day": 100.0, "max_cost_usd_per_run": 100.0}}
    )
    first = await run_case(case, "anthropic")
    second = await run_case(case, "anthropic")
    assert first["passed"], first["checks"]
    assert not second["passed"]
    assert len(calls) == 1
    assert first["cost_usd"] > 0 and second["cost_usd"] == 0
    assert first["provenance"]["budgets"]["max_cost_usd_per_day"] == 0.25
    assert first["provenance"]["accounting"]["durable"]
    assert first["provenance"]["accounting"]["ledger_id"] == second["provenance"]["accounting"]["ledger_id"]
    assert first["provenance"]["accounting"]["settled_usage"]


@pytest.mark.anyio
async def test_paid_eval_refuses_transient_accounting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RSF_DATABASE_URL", "sqlite://")
    case = load_cases(ROOT / "evals/golden/34-pit-clean-version.yaml")[0]
    with pytest.raises(InvalidInputError, match="durable accounting"):
        await run_case(case, "anthropic")
