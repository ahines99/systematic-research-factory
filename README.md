# Systematic Research Factory

A governed pipeline for systematic equity research. A trading hypothesis is frozen, tested on point-in-time data, audited for leakage and overfitting, and reviewed by a research committee. An LLM drafts evidence-cited reviews. Code computes and renders numeric claims; a deterministic gate and a separate human control decisions. Qualitative prose still needs review.

> **Status:** hosted research portfolio with a reproducible 240-run simulation study, a measured live-model comparison, and verified recovery/access controls. Live-model failures and human review boundaries are published explicitly. See [release status](https://github.com/ahines99/systematic-research-factory/releases), [hosted demo](https://systematic-research-factory.fly.dev/demo), and [delivery evidence and owner actions](docs/PORTFOLIO_STATUS.md).

[![CI](https://github.com/ahines99/systematic-research-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/ahines99/systematic-research-factory/actions/workflows/ci.yml)

**[Explore the portfolio](https://ahines99.github.io/systematic-research-factory/)** · [Case study](docs/CASE_STUDY.md) · [Quantitative research note](docs/research/note.md) · [Recorded reports](docs/samples/README.md) | [Live AI results](docs/live-evaluation/final-study/report.md) | [Hosted acceptance](docs/operations/2026-09-28/README.md)

The public reports use deterministic rules and scripted approval actors. All prices are simulated. They demonstrate workflow behavior, not live-model quality or real investment returns.

## The problem

Most backtests that look good are wrong in predictable ways:

- **Look-ahead bias:** using data the market couldn't have known yet, such as quarterly EPS treated as known at quarter-end rather than when the SEC accepted the filing.
- **Survivorship bias:** testing only on companies that still exist today.
- **P-hacking:** trying many variants and reporting the winner as if it were the only test.
- **Unsupported conclusions:** a persuasive write-up that no one can trace back to data.

Adding an LLM makes each of these easier to commit and harder to notice. This project shows what an LLM-assisted research workflow looks like when it is **auditable first**.

## Try it

```bash
uv sync --locked                                 # Python 3.12+; includes the dev tools
uv run rsf demo --out-dir var/reports            # six scenarios end to end in seconds, no API key
uv run rsf eval                                  # 37 golden cases, seven dimensions
uv run rsf run --file examples/experiments/earnings_drift.yaml
uv run rsf show <run_id> --format html --out var/run.html
uv run rsf replay <run_id>                       # deterministic replay requires the recorded code/dependency runtime
uv run pytest
```

On Windows, keep the checkout path short (or enable long paths): some dependencies install files deep enough to exceed the 260-character limit.

Serve it over MCP: `uv run rsf mcp-stdio` for a local client, or `uv run rsf serve` for Streamable HTTP with API keys (`uv run rsf keys create --owner you --role researcher`).

## How it works

```text
Hypothesis freeze → Data acquisition → Feature build → Backtest → Leakage audit
      → Statistical review → Economic rationale review → Implementation review
      → Research committee (deterministic gate + drafted memo + human decision)
```

| Layer | Role |
|---|---|
| Deterministic core | Point-in-time data access, features with lineage, backtest, leakage audit, statistics. All arithmetic lives here. |
| MCP server | 16 typed tools, 4 resources, 2 prompts. Every call is authenticated, checked against a policy table, audited, and fails with a typed error code. No trading tools exist. |
| Agent Skills | Four procedures plus bundled references; scoped review adapters and a targeted point-in-time evaluation. A scoped automated review is not a complete external red-team signoff. |
| Workflow state machine | Persists every step, resumes without re-running completed steps, retries transient failures, and pauses for humans, outages and budget caps. |

**Data:** a curated SEC-derived snapshot has 44 companies and 1,325 filing/version records (2019–2023), including 10 exits and 8 IPOs. Listing windows are filing-derived proxies; some EPS values are derived and revision categories are heuristic. Prices are simulated with a planted signal that reacts at SEC *acceptance* time. Period-end availability is an intentionally invalid counterfactual; its performance effect is measured, not assumed to be constant. The separate [frozen study](docs/research/note.md) uses fully synthetic worlds and reports all controls and sensitivities. See the [data sheet](docs/research/data-sheet.md) and [ADR-0003](docs/adr/0003-market-data-semi-synthetic.md).

## Why this is not just a chatbot

| Claim | Where it's enforced | Proven by |
|---|---|---|
| Structured numeric claims are artifact-bound | [research/](src/research_factory/research/) computes metrics; structured review references are resolved and formatted by [contract.py](src/research_factory/judgment/contract.py) | Hand-computed backtest/statistics tests and fabricated-value/reference regressions; prose meaning still needs review |
| Hypotheses can't be quietly edited, and overfitting can't hide | Content-hash experiment IDs; the [ledger](src/research_factory/services/ledger.py) counts every trial, including related trials frozen later or under another family name ([ADR-0008](docs/adr/0008-review-time-trial-counting.md)); database triggers make it append-only | [test_contracts.py](tests/test_contracts.py), golden case [08-overfit-many-trials](evals/golden/08-overfit-many-trials.yaml) |
| Time is enforced, not requested | `as_of` is required on every query ([pit.py](src/research_factory/data/pit.py)); the [leakage audit](src/research_factory/research/leakage.py) re-derives knowledge times from evidence and recomputes every feature value from the inputs it cites | [test_data.py](tests/test_data.py), golden cases 02–06 and 15 |
| Claims must cite evidence | Uncited or invented evidence IDs and unbound numeric claims are rejected; citation existence does not prove qualitative entailment ([contract.py](src/research_factory/judgment/contract.py)) | `test_uncited_or_invented_evidence_is_rejected` in [test_workflow.py](tests/test_workflow.py), golden case 21 |
| Humans approve decisions | A deterministic [gate](src/research_factory/services/approvals.py); the model's memo can't be more permissive than the gate; the approver must hold the role, can't be the requester, and can't approve against the gate | [test_workflow.py](tests/test_workflow.py), [test_http.py](tests/test_http.py), golden cases 23–25 |
| It's evaluated, not demoed | 37 [golden cases](evals/golden/), adversarial cases, scored on seven dimensions in CI | [test_demo_cli_evals.py](tests/test_demo_cli_evals.py) |
| Deterministic results are reproducible in their recorded runtime | Content-addressed snapshots, archived thresholds and source/dependency fingerprints; replay makes no model calls | `test_replay_from_archived_snapshot_is_byte_identical` in [test_demo_cli_evals.py](tests/test_demo_cli_evals.py) |

## Documentation

| Document | Contents |
|---|---|
| [docs/PORTFOLIO_STATUS.md](docs/PORTFOLIO_STATUS.md) | Current execution status, accepted decisions and exact owner/account actions |
| [docs/CASE_STUDY.md](docs/CASE_STUDY.md) · [docs/research/note.md](docs/research/note.md) | AI/quant case study, frozen simulation results and limitations |
| [docs/PORTFOLIO_ROADMAP.md](docs/PORTFOLIO_ROADMAP.md) | Remaining portfolio gaps, detailed assistant/owner actions, dependencies and acceptance criteria |
| [docs/architecture.md](docs/architecture.md) | Layers, the workflow, evidence and provenance, reproducibility, deployment |
| [docs/data_contracts.md](docs/data_contracts.md) | Every contract and table, generated from the code |
| [docs/threat_model.md](docs/threat_model.md) | Threats, mitigations, tests and residual risks |
| [docs/deployment.md](docs/deployment.md) · [docs/runbook.md](docs/runbook.md) | Fly.io + Neon + R2 setup, release, rollback, operations |
| [docs/ROADMAP.md](docs/ROADMAP.md) · [docs/adr/](docs/adr/README.md) | Tickets and architecture decisions |
| [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md) | The original specification and its acceptance checklist |
| [skills/](skills/) | The four Agent Skills |

## Scope

Research only. Live trading, order routing and broker connectivity are permanently out of scope. MIT licensed.
