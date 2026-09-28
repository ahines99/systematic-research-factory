# Systematic Research Factory

An AI engineering and quantitative research portfolio project by Alex Hines, developed with AI coding assistance. Public research implementation with independently reported offline controls, live-provider limitations and hosted acceptance evidence.

## Problem

A plausible backtest and a fluent explanation can conceal unavailable information, a selected universe or a large search over failed strategies. An LLM makes reviewing evidence easier, but it also introduces fabricated claims and authority confusion. The system makes those risks inspectable and gives deterministic controls the authority to stop a run.

## Engineering contribution

The application exposes typed MCP tools over local stdio and authenticated HTTP. A persisted nine-stage workflow freezes hypotheses, archives content-addressed inputs, computes features and returns, audits lineage, performs statistical review and produces a bounded committee memo. Separate requester and approver roles enforce the decision boundary. Durable leases, checkpoints, reservations and idempotency support recovery without duplicating paid calls or approvals.

Four Agent Skills supply research procedures. Their automated adapters have explicit scopes; the system returns missing-evidence results when it has not performed a broader analysis. Structured numerical references resolve to computed artifacts. Citation existence and schema validation do not prove general semantic correctness of model prose.

## Quantitative contribution

The [frozen study](research/note.md) evaluates 240 combinations across twenty held-out seed worlds, with null/planted controls, timing leakage and prespecified costs, delay and portfolio sensitivities. All results are published. Clean planted worlds passed the audit/statistical gate in 13/20 cases; clean null worlds in 0/20. The corresponding intervals are wide. The study demonstrates methodology with a known generator, not tradable alpha or a validated empirical earnings anomaly.

## Choices and tradeoffs

| Choice | Benefit | Limit |
|---|---|---|
| Simulated prices with known planted effects | Controlled answers for leakage and statistical tests | No real investment-performance inference |
| Rules provider for public demos | Free, predictable and inspectable visitor experience | No live-model quality claim |
| Content-addressed inputs and frozen hypotheses | Detect changed data/specifications and preserve lineage | Administrative storage controls still matter |
| Durable accounting and explicit uncertain-call reconciliation | Fail closed around paid-model ambiguity | Some interrupted calls need an operator |
| Strict replay identity | Prevent silent recomputation in incompatible environments | Requires preserving numerical runtime as well as source |
| Lightweight server-rendered UI and static showcase | Small operational surface and credential-free evidence | No SaaS dashboard or collaborative research workspace |

Hosted CI exposed a useful limitation: identical code and container image did not imply identical BLAS reduction bits across CPUs. The [follow-up](audits/2026-09-27/ci-followup.md) preserves the old evidence, documents the measured difference, strengthens new identities and separates exact replay from narrowly bounded historical numerical comparison.

## Evidence and claim boundaries

Review the [live CI checks](https://github.com/ahines99/systematic-research-factory/actions/workflows/ci.yml), [five-specialist audit and remediation](audits/2026-09-27/remediation.md), [golden cases](../evals/golden/), [raw study](research/results/study.json), and [sample reports](samples/README.md). The offline suite has 37 cases; its success is not evidence that skills improve a paid model. The [live evaluation protocol](live-evaluation-protocol.md) preserves development pilots and a frozen paired study. Live pilots exposed genuine failures: a task-specific verdict mismatch, an interrupted response, ambiguous numeric identifiers and incompatible model-generated metric references. Fixes preserve strict validation and publish negative outcomes; a valid schema or one successful targeted review does not establish general model reliability.

The current delivery and account dependencies are in [PORTFOLIO_STATUS.md](PORTFOLIO_STATUS.md). Operational acceptance and release status are recorded separately from the research results. The owner records the personal walkthrough, reviews blinded model outputs and observes actual hosting costs over time. Research only: no brokerage or trading capability exists.

## Interview walkthrough

Explain the clean run, then show why a timing leak is invalid even if performance improves. Trace a numerical claim to its artifact, explain how a later trial affects committee review, and distinguish a scripted approval from a real approver. Close with the CPU replay finding and the limitations of the simulation. These are concrete design decisions to defend, not claims of production financial performance.
