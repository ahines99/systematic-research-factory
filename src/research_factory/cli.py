"""``rsf`` command-line interface (RSF-024, RSF-048)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anyio
import yaml

from .auth import ApiKeyService, Principal, Role
from .config import Settings
from .domain.errors import DomainError
from .domain.project_models import ApprovalDecision, Experiment
from .observability import configure_logging
from .report import build_run_report, render_html, render_markdown
from .services.container import Services, build_services
from .workflows.faults import FaultRule
from .workflows.primary import engine_for_run, primary_engine


def _services(args: argparse.Namespace) -> Services:
    overrides: dict[str, Any] = {}
    if getattr(args, "database_url", None):
        overrides["database_url"] = args.database_url
    if getattr(args, "provider", None):
        overrides["model_provider"] = args.provider
    services = build_services(Settings(**overrides))
    for fault in getattr(args, "fault", None) or []:
        services.faults.rules.append(FaultRule.parse(fault))
    return services


def _load_experiment(path: str) -> Experiment:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Experiment.model_validate(doc)


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _summary(run: Any) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": str(run.status),
        "current_step": run.current_step,
        "reason": run.status_reason,
        "decision": str(run.decision) if run.decision else None,
    }


def cmd_init_db(args: argparse.Namespace) -> int:
    _services(args)
    print("database migrated")
    return 0


def cmd_freeze(args: argparse.Namespace) -> int:
    services = _services(args)
    record, created = services.ledger.freeze(_load_experiment(args.file), args.requested_by)
    _print({"experiment_id": record.experiment_id, "trial_number": record.trial_number, "created": created})
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    services = _services(args)
    record, _ = services.ledger.freeze(_load_experiment(args.file), args.requested_by)
    run = anyio.run(primary_engine(services).start, record.experiment_id, args.requested_by)
    _print(_summary(run))
    return 0 if str(run.status) != "failed" else 3


def cmd_resume(args: argparse.Namespace) -> int:
    services = _services(args)
    engine = engine_for_run(services, primary_engine(services).get_run(args.run_id))
    run = anyio.run(engine.advance, args.run_id, args.actor)
    _print(_summary(run))
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    services = _services(args)
    engine = engine_for_run(services, primary_engine(services).get_run(args.run_id))
    _print(_summary(engine.cancel(args.run_id, args.actor, args.reason)))
    return 0


def cmd_usage(args: argparse.Namespace) -> int:
    """Model spend today and per run, so budget pauses can be explained without SQL."""
    services = _services(args)
    budgets = services.settings.budgets
    print(f"spent today (UTC): ${services.budget.spent_today():.4f} of ${budgets.max_cost_usd_per_day:.2f}")
    print(f"guest live runs left today: {services.budget.guest_runs_remaining()}")
    for run in services.repos.runs.list(limit=args.limit):
        tokens, cost = services.repos.usage.totals_for_run(run.run_id)
        if tokens or cost:
            print(f"{run.run_id}  {tokens:>8} tokens  ${cost:.4f}  {run.status}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    services = _services(args)
    services.approvals.record(
        run_id=args.run_id,
        approver=args.approver,
        role="approver",
        decision=ApprovalDecision(args.decision),
        reason=args.reason,
    )
    run = anyio.run(primary_engine(services).advance, args.run_id, args.approver)
    _print(_summary(run))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    services = _services(args)
    report = build_run_report(services, args.run_id)
    text = {"json": lambda r: json.dumps(r, indent=2), "md": render_markdown, "html": render_html}[
        args.format
    ](report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    services = _services(args)
    for run in services.repos.runs.list(limit=args.limit):
        print(
            f"{run.run_id}  {run.project_type:18s} {run.status!s:13s} {run.current_step or '-':26s} {run.decision or ''}"
        )
    return 0


def cmd_lineage(args: argparse.Namespace) -> int:
    """Export feature lineage in the format read by skills/point-in-time-research/scripts/check_pit_timestamps.py."""
    services = _services(args)
    step = services.repos.steps.get(args.run_id, "Feature build")
    if step is None or step.artifact_evidence_id is None:
        raise DomainError("the run has no feature build artifact")
    lineage = services.evidence.load_json(step.artifact_evidence_id)["lineage"]
    Path(args.out).write_text(json.dumps(lineage), encoding="utf-8")
    print(f"wrote {len(lineage['rows'])} lineage rows to {args.out}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from .demo import manifest, record_demo

    services = _services(args)
    results = anyio.run(record_demo, services, args.scenario or None)
    out = Path(args.out_dir) if args.out_dir else None
    for r in results:
        print(
            f"{r.scenario:22s} {r.status:9s} {r.current_step or '-':24s} gate={r.gate or '-':20s} decision={r.decision or '-'}"
        )
        if out:
            out.mkdir(parents=True, exist_ok=True)
            report = build_run_report(services, r.run_id)
            (out / f"{r.scenario}.md").write_text(render_markdown(report), encoding="utf-8")
            (out / f"{r.scenario}.html").write_text(render_html(report), encoding="utf-8")
    if args.manifest:
        Path(args.manifest).write_text(
            json.dumps(manifest(results), indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"wrote {args.manifest}")
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    from .demo import replay_run

    services = _services(args)
    result = anyio.run(replay_run, services, args.run_id)
    _print(
        {
            "identical": result.identical,
            "replay_run_id": result.replay_run_id,
            "steps": {k: {"original": a, "replay": b} for k, (a, b) in result.compared.items()},
        }
    )
    return 0 if result.identical else 4


def cmd_keys(args: argparse.Namespace) -> int:
    services = _services(args)
    keys = ApiKeyService(services.repos.api_keys, services.clock)
    if args.keys_command == "create":
        key_id, key = keys.create(args.owner, Role(args.role))
        print(f"key_id: {key_id}\nkey:    {key}\nStore the key now; it is not shown again.")
    elif args.keys_command == "revoke":
        keys.revoke(args.key_id)
        print(f"revoked {args.key_id}")
    else:
        for row in services.repos.api_keys.list():
            print(
                f"{row['key_id']}  {row['owner']:20s} {row['role']:10s} created {row['created_at']:%Y-%m-%d}"
                f"{'  REVOKED' if row['revoked_at'] else ''}"
            )
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from .evals import run_eval_suite, write_scorecard
    from .judgment import prompts

    prompts.set_skills_enabled(not args.no_skills)
    scorecard = anyio.run(run_eval_suite, Path(args.cases), args.provider or Settings().model_provider)
    write_scorecard(scorecard, Path(args.out))
    print(f"{scorecard['passed']}/{scorecard['total']} cases passed; scorecard written to {args.out}")
    for dim, row in scorecard["dimensions"].items():
        print(f"  {dim:24s} {row['passed']}/{row['total']}")
    return 0 if scorecard["passed"] == scorecard["total"] else 5


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .http_app import create_app

    settings = Settings()
    configure_logging(settings.log_level, json=settings.log_json)
    uvicorn.run(
        create_app(_services(args)), host=args.host, port=args.port, proxy_headers=True, log_config=None
    )
    return 0


def cmd_stdio(args: argparse.Namespace) -> int:
    from .server import create_server

    create_server(_services(args), local_principal=Principal(args.as_user, Role(args.role))).run("stdio")
    return 0


def cmd_edgar(args: argparse.Namespace) -> int:
    from .data.edgar import EdgarClient
    from .data.edgar_universe import build_universe, write_snapshot

    settings = Settings()
    client = EdgarClient(
        settings.sec_user_agent,
        cache_dir=settings.edgar_cache_dir,
        requests_per_second=settings.sec_max_requests_per_second,
    )
    doc = build_universe(client)
    write_snapshot(doc, args.out)
    print(
        f"wrote {len(doc['securities'])} securities and {len(doc['filings'])} filing versions to {args.out}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rsf", description="Systematic Research Factory")
    p.add_argument("--database-url", help="override RSF_DATABASE_URL")
    p.add_argument(
        "--provider", choices=["rules", "anthropic"], help="judgment provider (default: RSF_MODEL_PROVIDER)"
    )
    p.add_argument("--log-level", default="WARNING")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create or migrate the database").set_defaults(func=cmd_init_db)
    s = sub.add_parser("freeze", help="freeze an experiment YAML into the ledger")
    s.add_argument("--file", required=True)
    s.add_argument("--requested-by", default="local-researcher")
    s.set_defaults(func=cmd_freeze)
    s = sub.add_parser("run", help="freeze and run the full workflow")
    s.add_argument("--file", required=True)
    s.add_argument("--requested-by", default="local-researcher")
    s.add_argument("--fault", action="append", help="inject a fault, e.g. data_source:timeout:1")
    s.set_defaults(func=cmd_run)
    s = sub.add_parser("resume", help="resume a paused run")
    s.add_argument("run_id")
    s.add_argument("--actor", default="local-researcher")
    s.set_defaults(func=cmd_resume)
    s = sub.add_parser("cancel", help="end a paused run for good")
    s.add_argument("run_id")
    s.add_argument("--reason", required=True)
    s.add_argument("--actor", default="local-researcher")
    s.set_defaults(func=cmd_cancel)
    s = sub.add_parser("usage", help="model spend today and per run")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_usage)
    s = sub.add_parser("approve", help="record a committee decision and resume")
    s.add_argument("run_id")
    s.add_argument("--decision", required=True, choices=[d.value for d in ApprovalDecision])
    s.add_argument("--reason", required=True)
    s.add_argument("--approver", required=True)
    s.set_defaults(func=cmd_approve)
    s = sub.add_parser("show", help="render a run report")
    s.add_argument("run_id")
    s.add_argument("--format", choices=["md", "html", "json"], default="md")
    s.add_argument("--out")
    s.set_defaults(func=cmd_show)
    s = sub.add_parser("runs", help="list recent runs")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_runs)
    s = sub.add_parser("lineage", help="export feature lineage for the timestamp-check script")
    s.add_argument("run_id")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_lineage)
    s = sub.add_parser("demo", help="record the demo scenarios")
    s.add_argument("--scenario", action="append")
    s.add_argument("--out-dir", help="write Markdown and HTML reports here")
    s.add_argument("--manifest", help="write the reproducibility manifest here")
    s.set_defaults(func=cmd_demo)
    s = sub.add_parser("replay", help="replay a run from its archived snapshot and compare artifacts")
    s.add_argument("run_id")
    s.set_defaults(func=cmd_replay)
    s = sub.add_parser("keys", help="manage API keys")
    ks = s.add_subparsers(dest="keys_command", required=True)
    k = ks.add_parser("create")
    k.add_argument("--owner", required=True)
    k.add_argument("--role", required=True, choices=[r.value for r in Role if r is not Role.GUEST])
    k = ks.add_parser("revoke")
    k.add_argument("key_id")
    ks.add_parser("list")
    s.set_defaults(func=cmd_keys)
    s = sub.add_parser("eval", help="run the golden evaluation suite")
    s.add_argument("--provider", choices=["rules", "anthropic"], default=argparse.SUPPRESS)
    s.add_argument("--cases", default="evals/golden")
    s.add_argument(
        "--no-skills", action="store_true", help="omit Agent Skills from judgment prompts (A/B test)"
    )
    s.add_argument("--out", default="var/scorecard.json")
    s.set_defaults(func=cmd_eval)
    s = sub.add_parser("serve", help="serve MCP over Streamable HTTP with API-key auth and the guest demo")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)
    s = sub.add_parser("mcp-stdio", help="serve MCP over stdio for a local client")
    s.add_argument("--as-user", default="local-operator")
    s.add_argument("--role", default="researcher", choices=[r.value for r in Role])
    s.set_defaults(func=cmd_stdio)
    s = sub.add_parser(
        "edgar", help="rebuild the EDGAR universe snapshot (network; needs RSF_SEC_USER_AGENT)"
    )
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_edgar)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level, json=False)
    try:
        return int(args.func(args))
    except DomainError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
