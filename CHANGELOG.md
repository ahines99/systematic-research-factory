# Changelog

All notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased] — v1.0 candidate

Everything for v1.0 is implemented and tested locally. Tagging `v1.0.0` waits on the owner actions in [docs/go-live-review.md](docs/go-live-review.md). There is no separate 0.1.0 release: the MVP and the v1.0 work ship together as `v1.0.0` ([ADR-0009](docs/adr/0009-production-defaults.md)).

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
- An evaluation harness with 30 golden cases scored on seven dimensions.
- SEC EDGAR adapter with a declared User-Agent, rate limiting, an SSRF allowlist and a disk cache. `acceptanceDateTime` was verified to be UTC.
- A security master for 44 companies (including 12 exits and 7 IPOs) and a committed universe snapshot with per-response provenance hashes.
- The `edgar-semi:v1` dataset: real filings with prices simulated from the real acceptance times (ADR-0003).
- Streamable HTTP serving with hashed, revocable API keys, four roles, guest rate limits, DNS-rebinding protection, `/demo` pages and capped guest live runs.
- Model-spend budgets per run and per day.
- Pre-recorded demo runs and exact replay from archived snapshots (`rsf replay`).
- Dockerfile pinned by digest, docker-compose stack, `fly.toml`, CI and release workflows with a dependency audit, SBOM and image scan.
- Docs: architecture, data contracts (generated), threat model, deployment, runbook, go-live review.

### Audit fixes (2026-09-23)
- **Access control:** resources check the HTTP caller, so guests can't read private runs; only a run's requester or an approver can resume or cancel it; guest data queries write no evidence; the proxy client-IP header is trusted only with `RSF_TRUST_PROXY_HEADERS`.
- **Spend:** guest live runs use the deterministic rules reviewer. The default model is `claude-opus-5`, with a $3.00 daily cap (ADR-0009).
- **Workflow:** run leases (one worker per run, takeover after expiry); unexpected errors pause with `INTERNAL`; retried steps supersede their old findings; step timeouts abandon blocking work; analysis runs resume as analysis runs; `rsf cancel`, the `cancel_run` tool and `rsf usage`.
- **Integrity:** one committee decision per pause; PostgreSQL `TRUNCATE` triggers on append-only tables (migration 0002); idempotent inserts.
- **Statistics:** the deflated Sharpe's trial variance never falls below sampling variance; the committee gates on the trial count at review time across renamed families (ADR-0008); the minimum track record length is reported.
- **Leakage audit:** six checks, adding lineage completeness and recomputation of every value from its cited evidence.
- **EDGAR data:** quarters keyed by period end; Q4 EPS from net income over weighted shares (split-robust, with a units guard); revisions tagged `restated` or `split_adjusted`; exits are price-neutral. The snapshot was rebuilt from the cache.
- **Experiments:** `hold_days` must equal `horizon_days`.
- **Evaluation:** golden cases 29 (an edited hypothesis is a new trial) and 30 (a delay-fragile signal); `rsf eval --no-skills`; a platform-aware demo manifest.
- **Operations:** GitHub Actions pinned to verified releases; the release image is scanned before it is pushed; Fly deploys with `--remote-only`; JSON logs from `rsf serve`.
