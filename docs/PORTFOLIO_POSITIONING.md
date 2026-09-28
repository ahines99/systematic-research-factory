# Canonical v1 portfolio positioning

Accepted by Alex Hines on 2026-09-28. Systematic Research Factory v1 is complete and presentation-ready. Additional platform features and empirical market-data research are not prerequisites for using this release in a portfolio or resume. Current delivery evidence and maintenance responsibilities remain in [PORTFOLIO_STATUS.md](PORTFOLIO_STATUS.md).

## Positioning and intended user

**Systematic Research Factory — Quantitative Research & AI Engineering**

A governed research platform connecting point-in-time data handling, statistical discipline, AI-assisted evidence review, durable workflow execution, and explicit approval controls.

The primary user is a systematic quantitative researcher working within a small team. The workflow is researcher → reproducible analysis → evidence review → independent decision. The professional positioning gives equal emphasis to quantitative research engineering and AI platform engineering.

Core message: **I built a research platform that tests whether conclusions are supported, preserves the evidence behind them, and exposes failures in both the quantitative workflow and the AI reviewer.**

## Approved resume entry

**Systematic Research Factory — Quantitative Research & AI Engineering**  
Python, NumPy, Pydantic, MCP, PostgreSQL, Docker, GitHub Actions, Fly.io

- Built and deployed a nine-stage research platform with frozen hypotheses, point-in-time data controls, deterministic leakage/statistical gates, evidence-bound AI reviews, and separate human approval.
- Executed a frozen 240-combination study across 20 held-out synthetic worlds; blocked all 40 constructed timing-leak controls and published complete results, uncertainty intervals, and sensitivity analyses.
- Implemented review-time multiple-testing controls, context-bound approvals, durable workflow recovery, and transactional model-budget reservations; verified cloud database restore and deployment rollback.

Links: [portfolio](https://ahines99.github.io/systematic-research-factory/) · [hosted demo](https://systematic-research-factory.fly.dev/demo) · [repository](https://github.com/ahines99/systematic-research-factory) · [v1.0.0 release](https://github.com/ahines99/systematic-research-factory/releases/tag/v1.0.0).

## Evidence behind the resume entry

| Claim | Inspectable evidence |
|---|---|
| Nine-stage governed workflow and separate approval | [Architecture](architecture.md), [approval policy and context binding](../src/research_factory/services/approvals.py), and [workflow regression tests](../tests/test_remediation_workflow.py) |
| Frozen 240-combination study and 40 blocked timing-leak controls | [Protocol](research/protocol.md), [all raw outcomes](research/results/study.json), and [research interpretation](research/note.md) |
| Review-time multiple-testing controls | [ADR-0008](adr/0008-review-time-trial-counting.md), [near-duplicate variance regression](../tests/test_research.py), and [review-time trial-count regression](../tests/test_audit_regressions.py) |
| Recovery and transactional model-budget reservations | [Workflow regression tests](../tests/test_remediation_workflow.py) and [budget/provider regression tests](../tests/test_remediation_judgment.py) |
| Cloud restore and deployment rollback | [Restore drill](operations/2026-09-28/restore-drill.json), [candidate rollback](operations/2026-09-28/rollback-acceptance.json), and [hosted acceptance](operations/2026-09-28/README.md) |

The rollback drill exercised two preserved candidate images and restored the intended candidate; it was not a rollback to a previous published release. The hosted restore drill recovered six demo runs, read twelve archived evidence objects, and replayed six deterministic stage artifacts exactly. These are specific acceptance observations, not a recovery-time SLA or a claim of production-scale usage.

## Claim boundaries

1. **Protocol freeze:** the protocol, seeds, configurations, and interpretation rules were frozen before execution. The runner generated the worlds during execution and recorded dataset hashes; a separately pre-published archive of all generated worlds is not claimed. See the [protocol](research/protocol.md).
2. **Statistical interpretation:** 13/20 clean planted worlds passed the combined audit/statistical gate under this generator and frozen design. This is not a calibrated general statistical-power estimate. All seven failed worlds missed the Newey–West threshold; six also missed Deflated Sharpe and one also missed the bootstrap condition. These overlapping failures were statistical, not leakage or model-review failures. See the [raw results](research/results/study.json) and [research note](research/note.md).
3. **AI usefulness:** targeted tasks demonstrated useful behavior, but every full-workflow observation missed at least one frozen acceptance criterion. Skills-on passed 15/21 versus 14/21 for Skills-off at more than twice the recorded cost. This is one model under two procedural-context conditions, not a provider comparison or proof of general Skills uplift. Human usefulness ratings remain uncollected. See the [live report](live-evaluation/final-study/report.md).
4. **Development attribution:** the project was developed with AI coding assistance; the defect stories include AI-assisted audit and remediation. Explain the implementation, verification, and assistance accurately rather than implying every finding was discovered unaided. See the [audit record](audits/2026-09-27/remediation.md).

All published strategy returns use simulated prices. SEC-derived filing records contribute real timestamp/version complications, not licensed historical market returns. No empirical alpha, investment performance, external customer adoption, production-scale throughput, or availability SLA is claimed. Public demonstrations use deterministic rules and scripted approval actors.

The simulation gate combines the leakage audit and statistical thresholds; the application committee additionally considers findings and requires separate approval. Experiment identity covers the hypothesis and backtest specification; data/runtime provenance and approval context are bound separately. Complete reporting of 240 planned combinations is a property of the frozen study and its publication, not a guarantee against experiments or selective reporting outside the system.

## Interview rehearsal

**Multiple-testing defect:** near-duplicate trial Sharpes could collapse the estimated variance and weaken the Deflated Sharpe adjustment. The documented audit example moved DSR from approximately 0.24 to 0.965 after 99 near-identical trials. The fix floors the variance and recomputes the related-trial count at committee review while preserving the original statistical artifact. Explain both the research risk and the remaining limitations of rule-based relatedness. [ADR-0008](adr/0008-review-time-trial-counting.md).

**Stale approval:** an approval must refer to the evidence and trial context actually reviewed. The implementation binds decisions to related trials, active findings, artifacts, and recorded thresholds, then checks that context when recording and consuming approval. A changed context requires renewed review; it cannot silently reuse the old decision. [Approval implementation](../src/research_factory/services/approvals.py) and [regression tests](../tests/test_remediation_workflow.py).

## Remaining presentation and observation tasks

| Task | State |
|---|---|
| Finalize resume/portfolio wording | Approved above; ready to copy into Alex's personal resume and external profiles |
| Rehearse the multiple-testing and stale-approval stories | Alex's personal preparation remains |
| Record a short walkthrough | [Script](demo-script.md) prepared; no personal video recorded |
| Complete blinded human ratings | [Packet](live-evaluation/final-study/blinded-review.md) prepared; rate before opening the separate key |
| Finish hosting-cost observation | [Cost log](operations/cost-observation.md) open; seven-day review scheduled for 2026-10-05 |

These tasks do not reopen v1 engineering scope. Routine dependency/security review, account ownership, and credential renewal continue as documented in the status and runbook.

## Separate v2 empirical study

Any empirical extension starts with a research question and its evidence requirements. Historical prices and stronger execution modeling belong to this separate phase; v1's synthetic controls and original evidence remain preserved.

1. Define one empirical question, hypothesis, evaluation scope, benchmark, and acceptance rules.
2. Specify data requirements and usage rights, including historical prices, corporate actions, delistings, and identifier history.
3. Audit fundamental-data suitability, including filing versions, derived EPS, coverage, and listing proxies.
4. Strengthen calendar and execution modeling to the level the question requires; make unsupported borrow, liquidity, impact, or capacity assumptions explicit or narrow the question.
5. Freeze the empirical protocol, development/evaluation split, planned variants, metrics, and reporting rules before examining evaluation outcomes.
6. Execute and publish every planned outcome, including failures, raw results, provenance, sensitivities, and limitations.

This is a future study sequence, not an active feature backlog or authorization to acquire paid market data. Additional platform work should follow a concrete requirement from that study.
