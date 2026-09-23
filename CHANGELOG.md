# Changelog

All notable changes to this project. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased] — v1.0 candidate

Everything for v1.0 is implemented and tested locally. Tagging `v1.0.0` waits on the owner actions in [docs/go-live-review.md](docs/go-live-review.md).

### Added
- SEC EDGAR adapter with a declared User-Agent, rate limiting, an SSRF allowlist and a disk cache. `acceptanceDateTime` was verified to be UTC.
- A security master for 44 companies (including 12 exits and 7 IPOs) and a committed universe snapshot with per-response provenance hashes.
- The `edgar-semi:v1` dataset: real filings with prices simulated from the real acceptance times (ADR-0003).
- Streamable HTTP serving with hashed, revocable API keys, four roles, guest rate limits, DNS-rebinding protection, `/demo` pages and capped guest live runs.
- Model-spend budgets per run and per day.
- Pre-recorded demo runs and exact replay from archived snapshots (`rsf replay`).
- Dockerfile pinned by digest, docker-compose stack, `fly.toml`, CI and release workflows with a dependency audit, SBOM and image scan.
- Docs: architecture, data contracts (generated), threat model, deployment, runbook, go-live review.

## [0.1.0] — 2026-09-23

First complete MVP.

### Added
- Contracts for hypotheses, backtest specs, experiments, runs, findings, evidence, audit events and approvals; content-hash experiment IDs.
- Deterministic synthetic world with a planted signal, look-ahead and survivorship traps.
- Persistence on SQLite/PostgreSQL with Alembic migrations and append-only triggers; content-addressed evidence.
- Point-in-time data access, features with knowledge-time lineage, backtest, leakage audit and statistical review (Newey-West, block bootstrap, deflated Sharpe).
- A nine-step workflow state machine with retries, timeouts, idempotent resume, fault injection and approval gates.
- Judgment steps with a schema-validated, evidence-cited contract; rules, scripted and Claude providers.
- An MCP server with 15 tools, 4 resources and 2 prompts; typed errors; per-call audit.
- Four Agent Skills with procedures, references and a timestamp-check script.
- The `rsf` CLI, run reports (JSON, Markdown, HTML) and demo scenarios.
- An evaluation harness with 28 golden cases scored on seven dimensions.
