# Repository audit — 2026-09-27

**Verdict: substantial implementation, passing baseline tests, but not release-ready. Engineering work remains in addition to the 12 owner-action tickets.** The claims that all implementation is complete and that only accounts/deployment remain are not supported by this audit.

Audited commit: `91e3023` on `main`, package version `0.1.0`. The worktree was clean at the start; no Git remote or tags were configured. Five specialist agents reviewed security/APIs, quantitative/data integrity, workflow/storage, delivery/operations, and skills/evaluations. A coordinating audit independently ran the baseline checks and consolidated overlapping findings. Specialists ran in two waves because of the concurrency limit.

The attached prior conversation was treated as historical context. Its claims were checked against the current repository. This audit changes documentation only; defects described below have **not** been fixed. No application source, release version, roadmap status, credentials, deployment or Git history was changed.

## What already exists

This is a working research-governance application, not an unfinished scaffold. At the audited commit there are 163 tracked files, about 10,344 source Python lines, 3,178 test lines, four skills with supporting material, and 30 golden cases.

| Area | Implemented work | Important qualification |
|---|---|---|
| Domain and identity | Typed contracts, immutable experiment identities, hypothesis freezing, research-family ledger and trial results | A frozen request is not fully protected against silently clipped data coverage |
| Research workflow | All nine steps, structured artifacts, deterministic gate, separate human approval | Approval freshness and checkpoint recovery have verified defects |
| Data | Synthetic fixtures and variants; SEC-derived snapshot for 44 securities, 1,325 filing/version records; PIT access and identifier history | Prices are simulated; some listing dates and EPS values are derived proxies |
| Features and backtest | EPS year-over-year, momentum, deliberate leakage fixture; lineage, quantile portfolios, delay, costs, turnover and IC | Execution can record fills after delisting; model is intentionally simplified |
| Statistical review | Sharpe, Newey-West t, block bootstrap, PSR/DSR, trial penalties, minimum observations, delay sensitivity | These validate a governance demo, not investable alpha on real prices |
| Leakage and quality | Time checks, universe checks, independent feature recomputation, malformed/stale-data scenarios | Non-finite recomputation can fail open |
| Interfaces | CLI; 16 MCP tools, four resources, two prompts; HTTP auth and demo pages | Public POST validation/body limits are inconsistent |
| Security | Hashed/revocable API keys, roles, guest restrictions, ownership checks, approval separation, escaped HTML | No new key-authentication bypass was found; several governance/spend controls still need repair |
| Persistence | SQLite/PostgreSQL repositories, migrations, append-only protections, content-addressed memory/file/S3 blobs | Crash atomicity, expired-worker writes and a file-write race remain |
| Reviews and skills | Rules and Anthropic providers, schema/citation validation, four procedural skills and PIT script | Citation existence does not establish factual support; PIT skill is absent from model-step mapping |
| Demo and replay | Six scenarios, JSON/Markdown/HTML reports, archived dataset replay | Replay invokes two judgment calls and uses current configuration |
| Delivery and operations | Lockfile, wheel/sdist, CI/release workflows, Docker/Compose/Fly configuration, runbook and ADRs | Container command is broken; published package and release-verification gaps remain |

## Fresh verification

| Check | Result from this audit |
|---|---|
| Python 3.14.5 pytest | **187 passed, 3 skipped**, 42.17 seconds |
| Python 3.12.10 pytest with coverage | **187 passed, 3 skipped**, 93.69 seconds |
| PostgreSQL 16.9 contract/workflow checks | **53 passed, 1 skipped**, 10.74 seconds; isolated temporary cluster, subsequently stopped |
| Ruff | Passed |
| Ruff formatting | 109 files already formatted |
| Strict mypy | Passed, 62 source files |
| Rules evaluation suite | **30/30 cases, 260/260 checks** across seven dimensions |
| Coverage | 92.87% statements, 78.89% branches; combined coverage metric 90.45% |
| Lock consistency | `uv lock --check --offline` passed |
| Dependency advisories | Fresh `pip-audit` of 66 locked runtime dependency records and extras returned no known vulnerabilities |
| Package build | Offline wheel/sdist build passed; wheel includes skills, snapshot and migrations |
| Installed-package evaluation | **Failed:** default `rsf eval` cannot locate `evals/golden` outside checkout |
| Selected tests from extracted sdist | **12 failed, 11 passed** because required repository assets were omitted |

The ordinary test skips concern PostgreSQL support. The separate database run exercises those paths; its one skip is the SQLite instance of a PostgreSQL-only TRUNCATE test. The 53-test run includes SQLite-backed workflow tests as well as PostgreSQL repository and full-workflow tests; it is not 53 distinct PostgreSQL-only tests.

Commands and machine-readable results are in [verification.json](verification.json), [scorecard.json](scorecard.json), [scorecard.md](scorecard.md), and [dependency-audit.json](dependency-audit.json). Full coverage and build scratch files remain under `var/audit-2026-09-27/`. Passing tests are useful baseline evidence, but the probes below demonstrate scenarios that the suite does not cover.

## Highest-priority engineering work

P1 here means fix before the affected release/production capability is enabled. P2 means a material correctness or reliability defect with narrower preconditions. This is an engineering priority, not a CVSS score. No critical remote compromise was demonstrated.

### A01 — P1: repair the container build command

`Dockerfile:16` contains the literal characters `\n` inside `RUN useradd ... rsf \n && ...`, rather than a continued newline. POSIX shell parsing supplies an extra `n` argument to `useradd`. This is a source-confirmed build blocker. Docker was unavailable, so this audit does not claim an actual image build was executed.

**Done when:** correct the instruction, build the image, run Compose, and smoke-test the non-root runtime, storage permissions, health endpoint and a complete workflow. Add a CI image-build check before release tagging. See the delivery report.

### A02 — P1: bind human approval to the current gate

`services/approvals.py:69` and `workflows/steps.py:790` evaluate the gate at different times. A weak run pauses with an approving gate; 99 related trials are then frozen; approval is recorded from the old findings; resume recomputes a rejecting DSR gate but completes with `decision=approve`.

**Observed:** `FINAL complete decision=approve gate=reject` through ordinary services, without a race or database tampering.

**Done when:** approval and consumption validate a fresh, versioned gate. A stale approval cannot finalize an approving decision against a rejecting/insufficient-evidence gate, including changes between record and resume. Define how stale immutable approvals are superseded without trapping the run behind the one-decision index. See SEC-01 in [security.md](security.md).

### A03 — P1: preserve terminal effects across crash recovery

`workflows/engine.py:229,262,264,283` saves a completed step before its terminal effects. Recovery skips that checkpoint without restoring `fail_run` or `run_decision`.

**Observed:** a post-checkpoint failure lets a period-end leakage run resume past the mandatory leakage stop to committee. The remaining blocking finding still prevents normal approval. Separately, a real approved primary run resumes to `complete` with `decision=None` while its committee artifact says `approve`.

**Done when:** atomically persist/reconcile the complete outcome, findings, run transition and audit record, with fault tests at each persistence boundary. See W1 in [workflow.md](workflow.md).

### A04 — P1 before paid use: make budgets and usage accounting enforceable

`services/budget.py:31` checks prior usage, not the pending call. A $0.01 run/day cap admitted a fake $0.10 response. Refusal/empty responses discard known usage. Abandoned timeout threads can finish paid work while the retry issues another call; the probe completed two fake $1 calls with zero recorded usage.

**Done when:** reserve budget transactionally before dispatch, constrain call allowance, settle known usage on success/refusal/error, reconcile late responses, and retain conservative reservations for uncertain outcomes. Test concurrent runs and timeout retries. If soft caps are intentional, state and bound the overshoot instead of calling them hard caps. See SEC-02/03 and W3.

### A05 — P1 for research integrity: enforce the frozen date range

Data acquisition and backtest search bounds silently clip requests to dataset coverage. A frozen end date of `2025-12-31` reached an approving committee recommendation using data ending `2023-12-29`, without a missing-coverage finding.

**Done when:** validate requested session coverage, including as-of before final close, before computation; reject or emit blocking insufficient evidence rather than silently test a different period. Include valid weekend endpoints. See QUANT-1 in [quant.md](quant.md).

### A06 — P1/P2: reject stale-worker commits after lease takeover

Leases renew before steps, but persistence is not fenced by current ownership. With a lease shorter than a step, two workers execute, and the expired worker commits the winning artifact. Process suspension creates the same ordering even with a longer configured lease.

**Done when:** fence writes with an ownership generation, heartbeat long work, reject stale commits, and validate timeout/lease settings. Test takeover during execution and immediately before persistence. This was reproduced with deliberately short leases, not a default-duration load test. See W2.

## Remaining correctness, reliability and verification backlog

| Work package | Evidence and impact | Required acceptance |
|---|---|---|
| **A07 — Honor reviewer uncertainty (P2)** | `needs_evidence=true` with a feasible verdict and missing-capacity question still yields gate approve (SEC-04) | Map the flag to an evidence finding/pause or reject contradictory outputs, in every review step |
| **A08 — Fail closed on non-finite lineage recomputation (P2)** | A fabricated momentum value `123456789` passes all six checks when cited pre-IPO prices recompute to NaN (QUANT-2) | Check finiteness and exact source/feature semantics; add dishonest-builder tests. This is an internal audit boundary, not a demonstrated remote-input exploit |
| **A09 — Model unfillable delayed trades (P2)** | Fills recorded after delisting: one synthetic and six EDGAR cases with supported daily rebalancing (QUANT-3) | Apply an execution-time fill policy with no hindsight changes to the decision universe; reconcile costs/exposure |
| **A10 — Define safe exact replay (P2)** | Replay invokes two judgment calls, uses current settings and lacks a full execution manifest; global snapshot pins contaminate concurrent runs (W5/W6) | Replay deterministic stages from archived configuration, reuse archived judgments, isolate per-run inputs, preserve code/dependency identity, and test an old release archive |
| **A11 — Fix concurrent file publication (P2)** | Identical writes share a PID-based temporary path; one writer raises FileNotFoundError (W4) | Unique temporary files and race-safe, integrity-checked publication; all concurrent writers succeed |
| **A12 — Harden public request validation (P2/P3)** | `/demo/live-run` parses bodies over 4 MiB; array/object scenarios return 500 (SEC-05/06) | Enforce the byte limit before parsing, including chunked bodies; invalid shapes consistently return typed 4xx |
| **A13 — Complete distribution contents (P2)** | Wheel lacks default eval cases; sdist ships tests without their required files | Package default eval resources or explicitly require an external path; build and test distributions from an unrelated directory |
| **A14 — Verify the deployed artifact (P2)** | Release scans a GHCR image, then Fly independently rebuilds from source | Deploy the scanned immutable digest or separately scan/attest the exact Fly artifact; exercise the pipeline |
| **A15 — Make evaluation failures meaningful (P2)** | Empty suite exits 0; unparseable INTERNAL MCP error can count as INVALID_INPUT; false numeric review claims pass fidelity checks | Fail on empty/missing suites and malformed errors; add wrong-value/wrong-evidence and actual adversarial-source cases; identify precisely what each dimension proves |
| **A16 — Make skill experiments attributable (P2)** | PIT skill is absent from model mapping; only top-level skill text is loaded; effective prompt changes can leave version hashes unchanged | Define the intended PIT exposure experiment, provide needed reference material, hash full effective inputs and record skill/model/configuration variants in baseline artifacts |
| **A17 — Correct completion/provenance claims (P2/P3)** | README/go-live overstate completion, numerical prose guarantees and replay; historical snapshot counts and old roadmap text are stale | Update status from actual evidence after fixes; distinguish deterministic artifacts from unverified model prose and derived data proxies |
| **A18 — Fix release preparation and smoke tests (P2)** | Following the documented version-only bump makes `uv lock --check --offline` fail; deployed smoke checks only unconditional `/healthz` | Regenerate/commit `uv.lock` with both version fields and changelog; require a tested commit and verify DB/blob access, MCP and demo behavior after deployment |
| **A19 — Preserve timestamp-checker input errors (P3)** | Invalid UTF-8 produces exit 1 and traceback instead of the documented bad-input exit 2/JSON (S7) | Catch decoding failures, preserve the error contract, and cover file/stdin malformed-input paths |

These packages consolidate overlapping specialist findings. Each component report includes source locations, observed output, reachability limits and acceptance criteria. They also list lower-priority inspection observations separately; those observations are not promoted to reproduced defects.

## Roadmap reconciliation and work requiring external setup

The ticket index really contains **65 `done`, 12 `owner`, 6 `skipped`**. Those are recorded statuses, not a fresh completion certification. Do not replace them with another precise completed count until the tickets are reconciled against this audit: one defect can reopen several tickets, and one ticket can contain several findings.

At minimum, revisit the acceptance of RSF-002 (distributions), 013 (blob concurrency), 018/020 (backtest/audit), 022/043/044/045 (workflow recovery), 032/033 (evals), 038/040/041/042 (judgments/provenance/approval), 058/059 (coverage/snapshots), 071 (spend), 074/075 (security/supply chain), and 077 (historical reproducibility). RSF-061 needs a code correction before it can be treated solely as an owner build check. RSF-034 needs an attributable skill experiment before a key alone can complete it.

| Existing owner tickets | Work still required | Dependency on this audit |
|---|---|---|
| RSF-004, RSF-060 | Create/push public GitHub repository, run CI including PostgreSQL, protect main | Local PostgreSQL is freshly verified; hosted CI/branch protection is not |
| RSF-061 | Build and exercise the container/Compose stack | Repair A01 first; Docker access is an environment prerequisite, not an inherently owner-only implementation task |
| RSF-065 | Configure R2 storage and its retention/bucket-lock policy | Verify real immutability behavior with the selected account policy |
| RSF-067, RSF-079 | Provision Fly/Neon/R2, configure secrets/hosts, deploy, seed six free demo runs and issue role-separated keys; measure idle hosting cost against the ticket's approximate $25/month ceiling | Close release blockers and use the corrected artifact pipeline |
| RSF-068 | Execute and time a database restore plus evidence/replay drill | Repair replay semantics; verify actual restored data, not just health |
| RSF-034, RSF-039 | Run and preserve model/skill baseline experiments with an API key | Fix attribution and spending first; use distinct output files for each variant |
| RSF-052 | Record a demo against the corrected behavior | Revise status/claims and script first |
| RSF-078 | Configure release credentials/environment, exercise tagged delivery and test rollback | Deploy a verified artifact and validate actual client/storage behavior |
| RSF-080 | Review evidence, bump both version declarations, regenerate/commit lockfile and update changelog, then tag `v1.0.0` | Separate pre-tag readiness approval from final post-deployment signoff; avoid requiring the first release to exist before its own tag |

Having no configured Git remote proves the current checkout is not connected to one; it does not establish whether the owner has created unrelated cloud resources. No owner accounts were inspected.

## Deliberate exclusions and scope limits

The six skipped tickets are RSF-053 (separate v0.1 release), RSF-070 (OpenTelemetry), RSF-072 (dashboards), RSF-076 (optional load test), RSF-081 (licensed price adapter) and RSF-083 (hosted OAuth). They are not automatically unfinished v1 requirements. Targeted concurrency tests needed to fix verified defects remain necessary even though a broad load-test project was skipped.

Live trading/order routing is permanently out of scope. Semi-synthetic prices, curated universe selection, weekday-only calendar, simplified turnover/execution costs and approximate listing windows are deliberate or documented limitations. They must remain visible in portfolio/demo claims. A real-market research product would need materially stronger data, execution and validation work; passing this demo does not establish live investment performance.

No paid model calls, live SEC ingestion, production storage operations, cloud deployment or GitHub publishing were performed. Dependency advisory queries were read-only network calls. Docker/Fly builds, real R2 retention, live Anthropic compatibility/costs, a hosted restore drill, and release/branch-protection behavior remain unverified. The audit did not certify the complete Git history as secret-free. No audit can establish the absence of all defects; this report records the examined boundaries and positive reproductions rather than treating test success as that guarantee.

## Recommended execution order

1. Fix approval freshness, checkpoint recovery and stale-worker writes; add the reproductions as regressions.
2. Repair paid-call accounting and uncertainty handling before any live baseline or paid traffic.
3. Fix date coverage, finite lineage checks and execution-day fills.
4. Repair Docker/distributions; make replay isolated and reproducible; harden public POST handling and blob concurrency.
5. Strengthen evaluation/skill attribution and release artifact verification; update the roadmap, README and go-live review from demonstrated results.
6. Run external CI, deployment, R2 retention, measured idle cost, restore and rollback checks; record model baselines/demo; prepare version/lock/changelog together, then complete the v1.0 release and post-deployment signoff.

## Specialist evidence

- [Security, APIs, approvals and budgets](security.md)
- [Quantitative methods, PIT and data](quant.md)
- [Workflow, persistence and replay](workflow.md)
- [Delivery, packaging and operations](ops.md)
- [Skills, evaluation and proof gaps](skills-evals.md)

The source paths and line numbers in these reports refer to commit `91e3023`. Audit artifacts are new documentation; no fixes were applied as part of the audit.
