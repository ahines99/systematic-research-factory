# Five-agent audit remediation

This record supersedes current completion claims, while preserving the [original audit](README.md) at commit `91e3023` as historical evidence. Five specialists covered security/judgments, workflow/storage, quantitative data, delivery/operations, and skills/evaluations; the coordinating agent integrated the changes and verification. Agents worked in waves under the concurrency limit.

The repository is an **unreleased research-governance candidate**, package version `0.1.0`. No commit, tag, push, paid model call or hosted deployment was performed. The worktree contains the reviewable implementation and regressions. The [go-live review](../../go-live-review.md) records external acceptance.

## Findings and disposition

| Finding | Implemented resolution | Regression / acceptance evidence |
|---|---|---|
| A01 — container build | Correct POSIX continuation, non-root UID 10001, writable persistent blobs, image build and Compose checks in CI | Real Linux image build and runtime smoke; `test_remediation_delivery.py`; final checks below |
| A02 — stale approval | Approval records and consumption bind a fresh gate context, including related trial inputs and active findings. A changed context requires a new immutable decision | `test_remediation_workflow.py` stale-before-record and changed-before-consumption cases |
| A03 — crash recovery | Checkpoint/findings/audit are atomic; `fail_run`, `run_decision` and `gate_context` are durable and reapplied on recovery. Known legacy terminal effects are recovered from stored artifacts | Fault injection before commit and after checkpoint, leakage-stop and approved-decision recovery |
| A04 — paid-call budgets | Database-serialized pending reservations, token preflight, constrained output, reviewed pricing, no automatic paid retry/fallback, usage settled inside late workers. Refusal/empty responses preserve usage; ambiguous calls block retries pending audited reconciliation | `test_remediation_judgment.py` includes independent SQLite connections and PostgreSQL concurrency, timeout/refusal and preflight tests; operator CLI tests |
| A05 — frozen date coverage | Every required weekday session and the final close must exist within `as_of`; weekend endpoints remain valid. No silently shortened backtest | `test_remediation_quant.py`, including full acquisition workflow |
| A06 — stale workers | Lease heartbeat and owner-fenced repository transactions reject stale writes, including evidence produced during a step; cancellation leaves an explicit resumable pause | Takeover during work and before checkpoint, stale source-evidence publication tests |
| A07 — explicit uncertainty | `needs_evidence` pauses every review even when its verdict is otherwise favorable | Judgment and workflow uncertainty regressions |
| A08 — non-finite/false lineage | Finite claimed/recomputed values, exact source/security/window/known filing version and decision-close semantics; orphan/duplicate lineage rejected | Dishonest-builder NaN, security, source-window, timestamp and EPS tests |
| A09 — impossible delayed fills | Execution-day listed/price checks, logged unfilled orders, cash settlement without hindsight reranking or phantom turnover/cost | Hand-checkable delisting cases and both built-in datasets |
| A10 — replay | Only six deterministic stages replay; archived thresholds and per-run snapshot pins; source/dependency/Python/platform identity required; no model or approval calls | Concurrent isolation and zero-model-call tests; preserved candidate archive. Actual earlier-release proof awaits a first published release |
| A11 — blob race | Unique temporary files and integrity-checked atomic publication | Concurrent identical file writes |
| A12 — public POST | Uniform pre-parse 4 MiB byte limit, including chunked/understated requests; closed typed scenario schema and malformed-input 4xx | `test_remediation_http.py` |
| A13 — distributions | Default golden cases bundled in wheel; source archive includes support files and stored replay fixture; installed CLI resolves package resources | Isolated wheel demo/eval and extracted sdist tests |
| A14 — deployed image identity | Full reusable CI gates release; scan/build once, authenticated registry copy, digest equality assertion, deploy exact digest | Workflow regression verifies invariant; real cloud registry copy/deployment remains external acceptance |
| A15 — evaluation meaning | Empty/malformed/unknown cases fail closed; unexpected MCP errors cannot masquerade as input failures; numeric claims are artifact-bound; actual input routes and exclusion cases tested | Skills/eval negative cases and expanded golden suite |
| A16 — skill attribution | All four skills have an explicit exposure path; selected references included, full prompt/schema/inputs hashed, per-case provenance and separate arm outputs. Structured attacks/dissent and rendered memo support scoped procedures | Targeted PIT treatment/control harness; full external red-team signoff and live model improvement are not claimed |
| A17 — accurate status/data claims | Current README/architecture/roadmap/go-live/changelog distinguish verified code from hosted acceptance and semantic limits. Snapshot counts/proxy assumptions corrected | Documentation reconciliation and link checks |
| A18 — release preparation/readiness | Both versions and lock consistency checked; documented lock regeneration; readiness checks database plus archived blobs; release smoke checks demo/MCP/authentication and expected version | Release guard and liveness-only negative tests; real container smoke/restart |
| A19 — checker input errors | Invalid UTF-8/file/stdin malformed input preserves JSON bad-input response and exit 2 | Skill checker regression cases |

## Secondary findings

- Removed the unused raw rationale and unbounded in-memory tool-call list; escaped untrusted text delimiters. These wrappers guide the model and are not the security boundary.
- Finding identity now includes provenance, severity, confidence, assumptions and metadata. Conflict-safe evidence/trial insertion verifies collisions. PostgreSQL testing caught and fixed indeterminate driver row counts using `INSERT ... RETURNING`.
- Ledger freeze plus audit, run creation plus audit, and workflow transition plus audit are transactional. Audit retrieval pages through all events. HTML reports include statistics, approvals and recorded usage.
- Dataset arrays, cached derived arrays and nested metadata are detached and immutable. Numeric quality checks cover infinite prices, invalid splits and EPS; non-finite EPS pauses before source hashing/serialization. Subsecond market-close handling is precise.
- Statistical artifacts include bootstrap method/block size/sample count/seed/confidence/interval method, HAC lag and variance source, allowing independent interval reconstruction.
- Quality, leakage and statistical CPU checks run outside the event loop, alongside existing feature/backtest offload. Regression tests demonstrate responsive timeout handling. Short synchronous database/serialization sections remain; this is not a large-input latency certification.
- Build tools/actions are pinned and release permissions are scoped by job; deployments are serialized. All release checks run on the tagged commit. Branch/environment protections still need GitHub configuration.
- Scanning the built image found additional high/critical OpenSSL and Python standard-library advisories that the Python dependency audit did not cover. The production image now uses pinned Python 3.14.7 and Debian OpenSSL/libssl3 `3.0.22-1~deb12u1`. The rebuilt image passes the existing high/critical gate; four lower-severity scanner matches remain, as recorded below.

## Verification

Verification was performed locally on Windows and in isolated Linux containers, with production package source frozen before creating the two candidate replay archives. Machine-readable results accompany this report.

| Check | Result |
|---|---|
| Windows Python 3.12.10 | Full suite: 286 passed, 4 skipped; coverage: 93.49% statements and 80.37% branches. This run preceded addition of the second replay-fixture parameter; both parameters subsequently passed focused delivery tests. |
| Windows Python 3.14.5 | Final full suite: 287 passed, 4 skipped, 63.82 seconds. |
| Linux Python 3.12.14 | 286 passed, 4 skipped; preserved Linux 3.12 archive replayed all six deterministic stages exactly. |
| Linux Python 3.14.7 | Final full suite: 287 passed, 4 skipped, 112.93 seconds; preserved Linux 3.14 archive replayed all six deterministic stages exactly. |
| Built distributions | Wheel installed into a fresh environment outside the checkout: all six demo scenarios and 37/37 default evaluation cases passed. Extracted source distribution under Python 3.12: 287 passed, 4 skipped, 68.65 seconds. |
| PostgreSQL 16.9 | 67 passed, 1 skipped across persistence, PostgreSQL, judgment and workflow tests, including independent-connection reservations and conflict-safe writes. |
| Offline rules evaluation | 37/37 cases, including 9 adversarial cases; 339/339 dimension checks. Zero live model cases. See the [scorecard](remediation-scorecard.md). |
| Static analysis and lock | Ruff checks and formatting: 92 files; strict mypy: 70 source files; `uv lock --check --offline`: passed. |
| Dependency advisory audit | 66 runtime dependency records, zero known advisories in this audit. See [dependency evidence](remediation-dependencies.json). |
| Actual production container | UID 10001 with PostgreSQL 16.15; readiness, demo, MCP, valid viewer authentication and invalid-key rejection passed. Original reports survived restart; replay was identical. |
| Image vulnerability policy | Grype 0.119.0 passed `--only-fixed --fail-on high` for image `sha256:f3d9c5f28273fb6e240e6cc363a0b6878fc28c571b62ce1d24013e36169fab89`. Three Medium and one Low match remain. See [scan evidence](remediation-image-scan.json). |
| Release action pins | All ten GitHub Action tags resolved to the official recorded commit SHAs. See [pin evidence](remediation-action-pins.json). |

The four ordinary skips are a SQLite-inapplicable TRUNCATE case and three PostgreSQL-only cases; the dedicated PostgreSQL run covers the latter. The matching Linux replay fixtures verify stored expected hashes; other platforms verify explicit rejection of an incompatible runtime. The initial Linux 3.14 run exposed an overly short heartbeat test timing window under host load. The test now uses controlled logical time and synchronizes with actual renewals; production fencing was unchanged.

The [verification record](remediation-verification.json) includes command outcomes, log digests, coverage, runtime source identity, candidate archive checksums and image details. Full local logs and built wheel/sdist artifacts are retained under `var/remediation/`. Documentation was finalized after package verification and the distributions rebuilt with identical executable payloads. Temporary database and Compose services were stopped after verification.

## Remaining acceptance and limits

1. Hosted GitHub CI, branch/environment protection, authenticated registry copy and Fly/Neon/R2 deployment need the owner's external setup. Real R2 retention, timed restore, rollback and measured idle cost remain pending.
2. Live Anthropic compatibility/billing and skill-on/off outcome evidence need a configured API account. Offline rules and fake-provider tests prove contracts and accounting paths, not the quality of a live model.
3. The stored archive is a reviewed candidate baseline. It proves replay without regenerating expected values during tests; it is not an archive from a previous published release. Preserve released images and archives for that future check.
4. Numeric references bind exact finite artifact fields and code-controlled labels. Arbitrary qualitative entailment remains unproven. Automated reviews declare their scope; they do not certify unavailable cost/concentration/capacity stress tests as completed.
5. Weekday calendar, simulated prices, curated universe, filing-derived listing windows, partly derived EPS, heuristic revision tags, constant weights and simplified costs remain research-demo assumptions. No result establishes investable alpha or trading performance.
6. A stale worker can leave an unreferenced write-once blob after a database failure; fenced transactions prevent it becoming current evidence. Provider reconciliation is a trusted local operator action requiring confirmation and an audit reason.
7. The image scan still reports Python advisories CVE-2026-17084, CVE-2026-15806 and CVE-2025-15367 (Medium), and CVE-2026-15310 (Low). Its listed fixes are Python 3.15 prereleases. They remain tracked residuals; passing the configured severity gate is not a claim that the image is vulnerability-free or that these findings are unreachable.

RSF-061 is locally verifiable and is no longer owner-only. RSF-077 remains externally incomplete for its literal previous-release criterion. Optional skipped work (broad load testing, licensed price adapter, OAuth, telemetry/dashboard projects and a separate MVP release) remains excluded; targeted correctness/concurrency work was completed within this remediation.
