# Architecture decision records

Each record captures one decision: its context, what was chosen, its consequences, and what would make us revisit it. Records are never edited after acceptance except to change their status. A reversal is a new ADR that supersedes the old one.

Copy [template.md](template.md) to start a new record.

| ADR | Decision | Status | Date |
|---|---|---|---|
| [0001](0001-persistence-sqlite-first.md) | SQLite for v0.1, PostgreSQL from M7 | Accepted | 2026-09-23 |
| [0002](0002-project-name.md) | Name the project "Systematic Research Factory" | Accepted | 2026-09-23 |
| [0003](0003-market-data-semi-synthetic.md) | Real SEC EDGAR filings with semi-synthetic prices | Accepted | 2026-09-23 |
| [0004](0004-authentication-api-keys.md) | API-key authentication for v1; hosted OAuth only for a Claude.ai connector | Accepted | 2026-09-23 |
| [0005](0005-workflow-state-machine.md) | Keep the in-house state machine; no workflow engine | Accepted | 2026-09-23 |
| [0006](0006-hosting.md) | Fly.io + Neon + Cloudflare R2, with hard model-spend caps | Accepted | 2026-09-23 |
| [0007](0007-v1-scope.md) | Define v1.0 as a portfolio-grade production cut; mark ops-heavy work optional | Accepted | 2026-09-23 |
| [0008](0008-review-time-trial-counting.md) | Count trials at review time; floor the Sharpe variance | Accepted | 2026-09-23 |
| [0009](0009-production-defaults.md) | Production defaults: Opus, $3/day cap, rules reviewer for guests, no v0.1 release | Accepted | 2026-09-23 |
