# Systematic Research Factory

A governed pipeline for systematic equity research. A trading hypothesis is frozen, tested on point-in-time data, audited for leakage and overfitting, and reviewed by a research committee. An LLM assists only at judgment steps and is never the system of record.

> **Status: pre-alpha (design + scaffold).** The architecture and specification are complete. The implementation is a stub MCP server with one passing test. See [Current state](IMPLEMENTATION_HANDOFF.md#current-state-as-of-2026-09-23) and the [roadmap](docs/ROADMAP.md).

## The problem

Most backtests that look good are wrong in predictable ways:

- **Look-ahead bias:** using data the market couldn't have known yet, such as a financial statement dated to its quarter-end rather than to when it was filed.
- **Survivorship bias:** testing only on companies that still exist today.
- **P-hacking:** trying many variants and reporting the winner as if it were the only test.
- **Unsupported conclusions:** a persuasive write-up that no one can trace back to data.

Adding an LLM makes each of these easier to commit and harder to notice. This project asks what an LLM-assisted research workflow looks like when it is designed to be **auditable first**.

## How it works

```text
Hypothesis freeze → Data acquisition → Feature build → Backtest → Leakage audit
      → Statistical review → Economic rationale review → Implementation review
      → Research committee (human approval)
```

| Layer | Role |
|---|---|
| Deterministic services | Point-in-time data access, feature build, backtesting, leakage audit, statistics. All arithmetic lives here and is tested. |
| MCP server | A narrow, typed tool interface for the model: every data query requires an `as_of` date; no trading tools exist. |
| Agent Skills | Version-controlled procedures for point-in-time research, statistics, red-teaming and committee review. |
| Workflow state machine | Owns run state, evidence, audit events, approvals and recovery, so the chat transcript never becomes the record. |

**Data.** Filings are real, from SEC EDGAR. Prices are simulated for the same companies, with a planted signal of known strength tied to when each filing actually became public. Because the right answer is known, the system can be scored on catching leaks, even on real filing data. Prices are always labelled as simulated, and no claim is made about real-world returns ([ADR-0003](docs/adr/0003-market-data-semi-synthetic.md)).

## Why this is not just a chatbot

These are **design commitments**. Each will link to the code and test that proves it once implemented (RSF-052).

- **The model never does the maths.** Returns and statistics, including the deflated Sharpe ratio adjusted for the number of trials, come from deterministic services with reference tests.
- **Hypotheses can't be quietly edited.** A frozen hypothesis is content-hashed into an experiment ID; changing it creates a new experiment, and the research ledger counts every trial.
- **Time is enforced, not requested.** Every data read requires `as_of` and is stored as evidence. The leakage audit checks each feature's knowledge time against its decision time.
- **Claims must cite evidence.** Model outputs are schema-validated, must reference stored evidence IDs, and return `NEEDS_EVIDENCE` rather than guess.
- **Humans approve decisions.** The workflow pauses for an approval record at the research committee. There is no path to order placement.
- **It's evaluated, not demoed.** A golden dataset with a planted signal and a planted leak scores every run on tool, evidence, calculation and permission fidelity.

## Quickstart (current scaffold)

Requires Python 3.12+. Until the package-layout fix (RSF-002) lands, an editable install doesn't work. Install the dependencies directly and run tests from the repo root:

```bash
python -m pip install "mcp[cli]>=2,<3" "pydantic>=2.9" pytest anyio
python -m pytest
```

## Repository

| Path | Contents |
|---|---|
| [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md) | Full specification: architecture, contracts, data model, evaluation, acceptance checklist |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 83 tickets across 10 milestones, from scaffold to v0.1 MVP to v1.0 production |
| [docs/adr/](docs/adr/README.md) | Architecture decision records: persistence, name, data, authentication, workflow, hosting, scope |
| [src/](src/) | MCP server stub and domain models |
| [skills/](skills/) | Agent Skill placeholders (real content in RSF-034–037) |
| [tests/](tests/) | MCP in-process tests |

## Scope

Research only. Live trading, order routing and broker connectivity are permanently out of scope.
