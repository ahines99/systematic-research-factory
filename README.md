# Systematic Research Factory

A governed pipeline for systematic equity research. A trading hypothesis is frozen, tested on point-in-time data, audited for leakage and overfitting, and reviewed by a research committee. An LLM assists only at judgment steps, can't compute numbers, and can't make decisions.

> **Status:** v0.1 released; v1.0 implemented and tested locally. Deployment is pending the owner's accounts ([go-live review](docs/go-live-review.md)). 152 tests, strict typing and 28 golden evaluation cases all pass.

## The problem

Most backtests that look good are wrong in predictable ways:

- **Look-ahead bias:** using data the market couldn't have known yet, such as quarterly EPS treated as known at quarter-end rather than when the SEC accepted the filing.
- **Survivorship bias:** testing only on companies that still exist today.
- **P-hacking:** trying many variants and reporting the winner as if it were the only test.
- **Unsupported conclusions:** a persuasive write-up that no one can trace back to data.

Adding an LLM makes each of these easier to commit and harder to notice. This project shows what an LLM-assisted research workflow looks like when it is **auditable first**.

## Try it

```bash
uv sync --locked                                 # Python 3.12+
uv run rsf demo --out-dir var/reports            # six scenarios end to end, ~2 seconds, no API key
uv run rsf eval                                  # 28 golden cases, seven dimensions
uv run rsf run --file examples/experiments/earnings_drift.yaml
uv run rsf show <run_id> --format html --out var/run.html
uv run rsf replay <run_id>                       # byte-identical replay from the archived snapshot
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
| MCP server | 15 typed tools, 4 resources, 2 prompts. Every call is authenticated, checked against a policy table, audited, and fails with a typed error code. No trading tools exist. |
| Agent Skills | Procedures for point-in-time research, statistics, red-teaming and the committee, loaded into the judgment prompts. |
| Workflow state machine | Persists every step, resumes without re-running completed steps, retries transient failures, and pauses for humans, outages and budget caps. |

**Data:** filings are real, from SEC EDGAR (44 companies, 2019–2023, including acquisitions, failures and IPOs). Prices are simulated for the same companies, with a planted signal of known strength that the market reacts to only at SEC *acceptance* time. A period-end leak therefore inflates results by a known amount, even on real filing timing, and the audit has to catch it. Prices are always labelled simulated; nothing here is a claim about real returns ([ADR-0003](docs/adr/0003-market-data-semi-synthetic.md)).

## Why this is not just a chatbot

| Claim | Where it's enforced | Proven by |
|---|---|---|
| The model never does the maths | [research/](src/research_factory/research/) computes everything; judgment output is [schema-validated](src/research_factory/judgment/contract.py) | [test_research.py](tests/test_research.py) (hand-computed backtest, the deflated-Sharpe worked example), independent recomputation in every [eval](src/research_factory/evals.py) case |
| Hypotheses can't be quietly edited | Content-hash experiment IDs; the [ledger](src/research_factory/services/ledger.py) counts every trial; database triggers make it append-only | [test_contracts.py](tests/test_contracts.py), golden case [08-overfit-many-trials](evals/golden/08-overfit-many-trials.yaml) |
| Time is enforced, not requested | `as_of` is required on every query ([pit.py](src/research_factory/data/pit.py)); the [leakage audit](src/research_factory/research/leakage.py) re-derives knowledge times from evidence | [test_data.py](tests/test_data.py), golden cases 02–06 and 15 |
| Claims must cite evidence | Uncited or invented evidence IDs are rejected ([contract.py](src/research_factory/judgment/contract.py)) | `test_uncited_or_invented_evidence_is_rejected` in [test_workflow.py](tests/test_workflow.py), golden case 21 |
| Humans approve decisions | A deterministic [gate](src/research_factory/services/approvals.py); the approver must hold the role, can't be the requester, and can't approve against the gate | [test_workflow.py](tests/test_workflow.py), [test_http.py](tests/test_http.py), golden cases 23–25 |
| It's evaluated, not demoed | 28 [golden cases](evals/golden/), 7 adversarial, scored on seven dimensions in CI | [test_demo_cli_evals.py](tests/test_demo_cli_evals.py) |
| Results are reproducible | Content-addressed evidence; replay from archived snapshots | `test_replay_from_archived_snapshot_is_byte_identical` in [test_demo_cli_evals.py](tests/test_demo_cli_evals.py) |

## Documentation

| Document | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Layers, the workflow, evidence and provenance, reproducibility, deployment |
| [docs/data_contracts.md](docs/data_contracts.md) | Every contract and table, generated from the code |
| [docs/threat_model.md](docs/threat_model.md) | 15 threats, each mapped to a mitigation and a test |
| [docs/deployment.md](docs/deployment.md) · [docs/runbook.md](docs/runbook.md) | Fly.io + Neon + R2 setup, release, rollback, operations |
| [docs/ROADMAP.md](docs/ROADMAP.md) · [docs/adr/](docs/adr/README.md) | Tickets and architecture decisions |
| [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md) | The original specification and its acceptance checklist |
| [skills/](skills/) | The four Agent Skills |

## Scope

Research only. Live trading, order routing and broker connectivity are permanently out of scope. MIT licensed.
