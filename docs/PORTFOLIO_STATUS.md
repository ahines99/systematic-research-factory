# Portfolio execution status

Updated 2026-09-28 UTC. Professional positioning gives equal emphasis to quantitative research engineering and AI platform engineering. The primary user is a systematic quantitative researcher working within a small team. The original gap assessment remains in the [roadmap](PORTFOLIO_ROADMAP.md); this document records current delivery.

**V1 is complete and presentation-ready.** The [canonical positioning](PORTFOLIO_POSITIONING.md) records the owner-approved resume entry, claim boundaries, interview stories, and remaining presentation tasks. Historical market data and stronger execution modeling belong to a separate v2 empirical study, driven by a defined research question.

[v1.0.0 is published](https://github.com/ahines99/systematic-research-factory/releases/tag/v1.0.0) from `c2b8babee11b13a011f901f8e421ee3b2a1fe3f4`. The [release workflow](https://github.com/ahines99/systematic-research-factory/actions/runs/36368156645) records tagged-source tests, scanned-digest deployment and final browser acceptance. All downloaded release checksums and 121 evidence entries were verified.

The [portfolio](https://ahines99.github.io/systematic-research-factory/) and [hosted demo](https://systematic-research-factory.fly.dev/demo) are online. Public demos use deterministic rules and scripted approvers. All prices are simulated; neither the demo nor the simulation study establishes tradable alpha.

## Delivered evidence

| Area | Result |
|---|---|
| Engineering | Five-specialist audit remediated; 302 local tests passed, four PostgreSQL-specific skips covered separately; ten protected-branch CI checks passed before hosted deployment. |
| Quant research | Frozen 240-combination study, twenty held-out worlds, all raw results and inspected plots. Clean null gate passes 0/20; clean planted passes 13/20; all forty leaky controls blocked. |
| Live AI evaluation | The [frozen comparison](live-evaluation/final-study/report.md) completed all 42 observations: Skills-on 15/21, Skills-off 14/21. Development pilots remain separately labeled. Rejected outputs, costs and latency failures remain failures. No general skills-uplift or unattended-model-reliability claim. |
| Deployment | One shared CPU/1 GiB Fly machine in iad, dedicated Neon database and nonadministrative role, private R2 storage; deploy uses a scanned immutable image digest. |
| Database | Neon PostgreSQL 18.6: 67 contract tests passed, one SQLite-only parameter skipped; client TLS verified. Disposable validation branch removed. |
| Retention | R2 ninety-day lock rejects overwrite and delete with HTTP 409; original object bytes preserved. Owner accepted Neon's verified six-hour point-in-time recovery window for this portfolio. |
| Recovery | Isolated point-in-time restore recovered all six demos; twelve archived objects read and six deterministic artifacts replayed exactly. Completed in 19.69 seconds including cleanup. |
| Access | Official MCP SDK exercised all four roles; authenticated hypothesis freeze/backtest/report read and guest private-report denial passed. Viewer rotation verified revoked-key rejection and replacement-key access. |
| Rollback | Both preserved candidate images deployed and passed original-report checks; intended v1 restored. Total 99.34 seconds. |
| Runtime | Stop/start preserved all six reports; one cold readiness observation was 7.266 seconds. Application RSS was about 190 MiB after restart, not a load-test peak. |
| Presentation | Desktop/mobile pages and report navigation passed browser checks; screenshots visually inspected. The recovery-card naming collision is fixed in v1; the earlier observation remains in the dated acceptance record. |
| Delivery | CI checks Python 3.12/3.13/3.14, PostgreSQL, packages, container, dependency vulnerabilities, offline evaluations and preserved historical artifact comparison. Release automation assembles distributions, checksums, evidence and an SBOM. |

See [hosted acceptance and immutable evidence](operations/2026-09-28/README.md), [current CI](https://github.com/ahines99/systematic-research-factory/actions/workflows/ci.yml), and the [release review](go-live-review.md) for exact revisions and publication state. Historical test counts and earlier failed probes remain dated records, not current account-setup tasks.

## Accepted operating limits

Hosted model dispatch remains capped at $1/run and $3/UTC day; guests use free deterministic rules. The finite local evaluation was separately authorized for a $5 cumulative pilot and $20 UTC-day allowance, retaining a $20 lifetime total inclusive of every earlier call and unresolved hold. The original lost response retains its full $0.99998 reservation; provider billing remains unknown and the owner instructed continuation without reconciliation.

Hosting target: $25/month, with review at a $20 projected monthly cost. One shared CPU/1 GiB in iad, Neon Free with six-hour restore, R2 Standard with ninety-day retention; no custom domain, market-data subscription or dedicated IPv4. Actual seven-day bills cannot be inferred from configuration or one runtime measurement.

## Owner actions

The resume/portfolio wording is finalized in the [canonical entry](PORTFOLIO_POSITIONING.md#approved-resume-entry). Copy it into personal application materials and rehearse the multiple-testing defect and stale-approval stories. The following personal and time-dependent work does not block presenting v1:

1. **Personal review and narration:** read the [case study](CASE_STUDY.md) and [research note](research/note.md), then use the [recording script](demo-script.md) for a short walkthrough. Explain simulation limits, the clean/leaky controls and the failed live-model cases. Add the video URL when published; no video or personal endorsement has been fabricated.
2. **Human model ratings:** rate the [blinded sample](live-evaluation/final-study/blinded-review.md) for usefulness, evidence support and clarity before opening its separate arm key. These ratings are distinct from automated pass/fail and remain uncollected until you supply them.
3. **Ongoing ownership:** observe actual Fly/Neon/R2 costs over seven days using the [cost log](operations/cost-observation.md); retain account access and review security updates. The app-scoped GitHub Fly deployment token expires after ninety days and must be renewed before then.

The owner authorized finalization and publication; the assistant records the concrete technical release review and post-deployment checks. No personal sample ratings or narration are inferred from that authorization.

Credentials are already configured locally and on the relevant platforms. No additional Anthropic, Neon, Fly or R2 account creation is required. Local operator credentials remain in ignored files; their values must never be copied into documentation or screenshots.

## Honest limits

The image scan retains three Medium and one Low Python advisories, tracked in the [risk register](security-risk-register.md). No High/Critical matches were present in the deployed candidate scan. Model output validation does not establish semantic correctness; the live study includes failures. The project provides no trading tools, production availability SLA, or on-call service. A seven-day observation requires elapsed time. Replaying an actual prior published release becomes testable after a subsequent release exists; the current exact restore replay is a different, completed check.
