"""Run reports (RSF-049): one structured document, rendered to Markdown or HTML."""

from __future__ import annotations

import html
from typing import Any

from .domain.errors import NotFoundError
from .services.approvals import compute_gate
from .services.container import Services

SEVERITY_ORDER = {"blocking": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def build_run_report(services: Services, run_id: str) -> dict[str, Any]:
    repos = services.repos
    run = repos.runs.get(run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    record = services.ledger.get(run.experiment_id)
    findings = repos.findings.list_for_run(run_id)
    steps = repos.steps.list(run_id)
    tokens, cost = repos.usage.totals_for_run(run_id)
    hyp = record.experiment.hypothesis
    spec = record.experiment.backtest
    stats: dict[str, Any] | None = None
    backtest: dict[str, Any] | None = None
    for s in steps:
        if s.artifact_evidence_id and s.step == "Statistical review":
            doc = services.evidence.load_json(s.artifact_evidence_id)
            stats = {
                k: doc[k]
                for k in (
                    "n_obs",
                    "sharpe_annualized",
                    "newey_west_t",
                    "deflated_sharpe",
                    "n_trials",
                    "bootstrap_ci",
                    "ic_mean",
                    "turnover_mean",
                    "cost_drag_annualized",
                    "passed",
                )
            }
        if s.artifact_evidence_id and s.step == "Backtest":
            backtest = services.evidence.load_json(s.artifact_evidence_id)["summary"]
    return {
        "format": "rsf-run-report/1",
        "run": run.model_dump(mode="json"),
        "experiment": {
            "experiment_id": record.experiment_id,
            "research_family": record.research_family,
            "trial_number": record.trial_number,
            "hypothesis_id": hyp.hypothesis_id,
            "statement": hyp.statement,
            "feature": hyp.feature.name,
            "timing_basis": str(hyp.feature.timing_basis),
            "dataset": hyp.universe.dataset,
            "universe_mode": str(hyp.universe.mode),
            "backtest": spec.model_dump(mode="json"),
        },
        "gate": compute_gate(findings).to_dict(),
        "steps": [
            {
                "step": s.step,
                "status": str(s.status),
                "attempts": s.attempts,
                "artifact_evidence_id": s.artifact_evidence_id,
                "error_code": s.error_code,
                "error_message": s.error_message,
            }
            for s in steps
        ],
        "findings": sorted(
            (f.model_dump(mode="json") for f in findings),
            key=lambda f: (SEVERITY_ORDER[f["severity"]], f["step"]),
        ),
        "backtest": backtest,
        "statistics": stats,
        "approvals": [a.model_dump(mode="json") for a in repos.approvals.list_for_run(run_id)],
        "evidence": [
            {
                "evidence_id": ref.evidence_id,
                "step": step,
                "source_type": ref.source_type,
                "source_uri": ref.source_uri,
                "content_hash": ref.content_hash,
            }
            for step, ref in repos.evidence.list_for_run(run_id)
        ],
        "audit": [
            {
                "event_id": e.event_id,
                "at": e.created_at.isoformat(),
                "step": e.step,
                "event_type": e.event_type,
                "actor": e.actor,
            }
            for e in services.audit.events(run_id)
        ],
        "usage": {"tokens": tokens, "cost_usd": round(cost, 6)},
        "prices_simulated_notice": "Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    run, exp = report["run"], report["experiment"]
    lines = [
        f"# Run {run['run_id']}",
        "",
        f"**Status:** {run['status']}"
        + (f" · **Decision:** {run['decision']}" if run.get("decision") else ""),
        f"**Reason:** {run.get('status_reason') or '-'}",
        f"**Experiment:** `{exp['experiment_id']}` (trial {exp['trial_number']} of `{exp['research_family']}`)",
        f"**Hypothesis:** {exp['statement']}",
        f"**Feature:** `{exp['feature']}` ({exp['timing_basis']} timing) on `{exp['dataset']}` ({exp['universe_mode']} universe)",
        "",
        f"> {report['prices_simulated_notice']}",
        "",
        f"## Gate: {report['gate']['recommendation']}",
        *[f"- {r}" for r in report["gate"]["reasons"]],
        "",
        "## Steps",
        "| Step | Status | Attempts | Artifact |",
        "|---|---|---|---|",
        *[
            f"| {s['step']} | {s['status']}{' (' + s['error_code'] + ')' if s['error_code'] else ''} | {s['attempts']} | "
            f"`{s['artifact_evidence_id'] or '-'}` |"
            for s in report["steps"]
        ],
    ]
    if report["statistics"]:
        st = report["statistics"]
        lines += [
            "",
            "## Statistics",
            f"- Observations: {st['n_obs']}; annualized Sharpe {st['sharpe_annualized']:.2f}; Newey-West t {st['newey_west_t']:.2f}",
            f"- Deflated Sharpe {st['deflated_sharpe']:.3f} across {st['n_trials']} trial(s); "
            f"bootstrap CI [{st['bootstrap_ci'][0]:.2f}, {st['bootstrap_ci'][1]:.2f}]",
        ]
    lines += ["", "## Findings"]
    for f in report["findings"]:
        cites = ", ".join(f"`{e}`" for e in f["evidence_ids"]) or "none"
        lines.append(
            f"- **[{f['severity']}] {f['title']}** ({f['step']}): {f['statement']} Evidence: {cites}"
        )
    if report["approvals"]:
        lines += ["", "## Approvals"]
        lines += [
            f"- {a['approver']}: **{a['decision']}**: {a['reason']} ({a['created_at']})"
            for a in report["approvals"]
        ]
    lines += ["", "## Audit trail", "| # | Time | Step | Event | Actor |", "|---|---|---|---|---|"]
    lines += [
        f"| {e['event_id']} | {e['at']} | {e['step']} | {e['event_type']} | {e['actor']} |"
        for e in report["audit"]
    ]
    return "\n".join(lines) + "\n"


def render_html(report: dict[str, Any]) -> str:
    e = html.escape
    run, exp = report["run"], report["experiment"]
    rows = "".join(
        f"<tr><td>{e(s['step'])}</td><td class='st-{e(s['status'])}'>{e(s['status'])}</td>"
        f"<td>{s['attempts']}</td><td><code>{e(s['artifact_evidence_id'] or '-')}</code></td></tr>"
        for s in report["steps"]
    )
    findings = "".join(
        f"<li class='sev-{e(f['severity'])}'><strong>[{e(f['severity'])}] {e(f['title'])}</strong> "
        f"<span class='step'>{e(f['step'])}</span><br>{e(f['statement'])}"
        f"<div class='cite'>{' '.join('<code>' + e(x) + '</code>' for x in f['evidence_ids'])}</div></li>"
        for f in report["findings"]
    )
    audit = "".join(
        f"<tr><td>{a['event_id']}</td><td>{e(a['at'])}</td><td>{e(a['step'])}</td><td>{e(a['event_type'])}</td>"
        f"<td>{e(a['actor'])}</td></tr>"
        for a in report["audit"]
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Run {e(run["run_id"])}</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#5c5c5c;--line:#ddd;--block:#b42318;--high:#c4320a;--med:#b54708;--ok:#067647}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#eee;--muted:#aaa;--line:#333;--block:#f97066;--high:#fd853a;--med:#fdb022;--ok:#47cd89}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}}
code{{font-size:12px}}.step,.cite{{color:var(--muted);font-size:12px}}li{{margin:6px 0}}
.sev-blocking strong{{color:var(--block)}}.sev-high strong{{color:var(--high)}}.sev-medium strong{{color:var(--med)}}
.st-completed{{color:var(--ok)}}.st-failed{{color:var(--block)}}.notice{{border-left:3px solid var(--med);padding-left:8px;color:var(--muted)}}
.wrap{{overflow-x:auto}}
</style></head><body>
<h1>Run <code>{e(run["run_id"])}</code></h1>
<p><strong>Status:</strong> {e(run["status"])} {("· <strong>Decision:</strong> " + e(run["decision"])) if run.get("decision") else ""}<br>
<strong>Reason:</strong> {e(run.get("status_reason") or "-")}</p>
<p><strong>Hypothesis:</strong> {e(exp["statement"])}<br><strong>Feature:</strong> <code>{e(exp["feature"])}</code>
({e(exp["timing_basis"])} timing) · <strong>Dataset:</strong> <code>{e(exp["dataset"])}</code> · trial {exp["trial_number"]}
of <code>{e(exp["research_family"])}</code></p>
<p class="notice">{e(report["prices_simulated_notice"])}</p>
<h2>Gate: {e(report["gate"]["recommendation"])}</h2><ul>{"".join("<li>" + e(r) + "</li>" for r in report["gate"]["reasons"])}</ul>
<h2>Steps</h2><div class="wrap"><table><tr><th>Step</th><th>Status</th><th>Attempts</th><th>Artifact</th></tr>{rows}</table></div>
<h2>Findings</h2><ul>{findings}</ul>
<h2>Audit trail</h2><div class="wrap"><table><tr><th>#</th><th>Time</th><th>Step</th><th>Event</th><th>Actor</th></tr>{audit}</table></div>
</body></html>"""
