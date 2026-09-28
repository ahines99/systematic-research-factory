# Changelog

All notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased] — v1.0 candidate

This is an unreleased candidate. Current local evidence and external acceptance are recorded in the [remediation report](docs/audits/2026-09-27/remediation.md) and [go-live review](docs/go-live-review.md). There is no separate 0.1.0 release: the MVP and the v1.0 work ship together as `v1.0.0` ([ADR-0009](docs/adr/0009-production-defaults.md)).

### Hosted acceptance fixes
- Distinguish the recovery demo using its recorded acquisition retry; show the latest run for each scenario after reseeding.
- Require six distinct scenario cards in desktop/mobile browser acceptance.
- Prepare matching `1.0.0` package declarations and lock metadata; tagging remains a separate release action.

### Added
- Contracts for hypotheses, backtest specs, experiments, runs, findings, evidence, audit events and approvals; content-hash experiment IDs.
- Deterministic synthetic world with a planted signal, look-ahead and survivorship traps.
- Persistence on SQLite/PostgreSQL with Alembic migrations and append-only triggers; content-addressed evidence.
- Point-in-time data access, features with knowledge-time lineage, backtest, leakage audit and statistical review (Newey-West, block bootstrap, deflated Sharpe).
- A nine-step workflow state machine with retries, timeouts, idempotent resume, fault injection and approval gates.
- Judgment steps with a schema-validated, evidence-cited contract; rules, scripted and Claude providers.
- An MCP server with 16 tools, 4 resources and 2 prompts; typed errors; per-call audit.
- Four Agent Skills with procedures, references and a timestamp-check script.
- The `rsf` CLI, run reports (JSON, Markdown, HTML) and demo scenarios.
- An evaluation harness with 37 golden cases scored on seven dimensions.
- SEC EDGAR adapter with a declared User-Agent, rate limiting, an SSRF allowlist and a disk cache. `acceptanceDateTime` was verified to be UTC.
- A security master for 44 companies (including 10 exits and 8 IPOs; listing windows are filing-derived proxies) and a committed universe snapshot with per-response provenance hashes.
- The `edgar-semi:v1` dataset: real filings with prices simulated from the real acceptance times (ADR-0003).
- Streamable HTTP serving with hashed, revocable API keys, four roles, guest rate limits, DNS-rebinding protection, `/demo` pages and capped guest live runs.
- Model-spend budgets per run and per day.
- Pre-recorded demo runs and exact replay from archived snapshots (`rsf replay`).
- Dockerfile pinned by digest, docker-compose stack, `fly.toml`, CI and release workflows with a dependency audit, SBOM and image scan.
- Docs: architecture, data contracts (generated), threat model, deployment, runbook, go-live review.

### Audit remediation (2026-09-27)
- Fresh gate-bound approvals, durable terminal checkpoints, heartbeat and owner-fenced persistence, conflict-safe evidence/trial publication, and complete audit pagination.
- Transactional paid-call reservations and bounded dispatch; refusal/late usage settlement; explicit audited reconciliation for uncertain outcomes.
- Frozen session coverage, finite and semantically bound lineage, immutable dataset buffers, and execution-time handling of unfillable orders.
- Deterministic-only replay using archived settings and a recorded source/dependency runtime; isolated snapshot pins and a stored candidate archive.
- Uniform streaming request limits and input validation; database/blob readiness; HTML statistics, usage and approval records.
- Complete distribution resources, corrected non-root Docker build, full release checks and deployment of the scanned image digest.
- Production container upgraded to pinned Python 3.14.7 and patched Debian OpenSSL after actual image scanning; the high/critical policy passes, with four lower-severity advisories tracked in the remediation report.
- Artifact-bound numeric reviews, explicit uncertainty handling, scoped skill/reference payloads, attributable evaluations and robust malformed-input failures.
- Corrected status and data provenance claims; hosted deployment, live provider experiments and operational drills remain pending.

### Historical audit fixes (2026-09-23)
- **Access control:** resources check the HTTP caller, so guests can't read private runs; only a run's requester or an approver can resume or cancel it; guest data queries write no evidence; the proxy client-IP header is trusted only with `RSF_TRUST_PROXY_HEADERS`.
- **Spend:** guest live runs use the deterministic rules reviewer. The default model is `claude-opus-5`, with a $3.00 daily cap (ADR-0009).
- **Workflow:** run leases (one worker per run, takeover after expiry); unexpected errors pause with `INTERNAL`; retried steps supersede their old findings; step timeouts abandon blocking work; analysis runs resume as analysis runs; `rsf cancel`, the `cancel_run` tool and `rsf usage`.
- **Integrity:** one committee decision per pause; PostgreSQL `TRUNCATE` triggers on append-only tables (migration 0002); idempotent inserts.
- **Statistics:** the deflated Sharpe's trial variance never falls below sampling variance; the committee gates on the trial count at review time across renamed families (ADR-0008); the minimum track record length is reported.
- **Leakage audit:** six checks, adding lineage completeness and recomputation of every value from its cited evidence.
- **EDGAR data:** quarters keyed by period end; Q4 EPS from net income over weighted shares (split-robust, with a units guard); revisions tagged `restated` or `split_adjusted`; exits are price-neutral. The snapshot was rebuilt from the cache.
- **Experiments:** `hold_days` must equal `horizon_days`.
- **Evaluation:** golden cases 29 (an edited hypothesis is a new trial) and 30 (a delay-fragile signal); `rsf eval --no-skills`; a platform-aware demo manifest.
- **Operations:** GitHub Actions pinned to verified releases; the release image is scanned before it is pushed; the then-current Fly path used `--remote-only` (superseded by immutable digest deployment above); JSON logs from `rsf serve`.
