# ADR-0001: SQLite for v0.1, PostgreSQL from M7

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-011, RSF-060

## Context
The original spec named PostgreSQL as the workflow source of truth from day one. For v0.1, running everything locally, a database server adds setup cost for every contributor and every CI run, and brings no benefit: one process, no concurrent writers, fixture data only.

## Decision
- Use SQLAlchemy 2 with Alembic migrations, using only portable column types. UUIDs are stored as strings; JSON uses SQLAlchemy's `JSON` type.
- Use SQLite as the v0.1 and zero-setup developer default.
- Use PostgreSQL (Neon, see [ADR-0006](0006-hosting.md)) for deployed environments from M7. From RSF-060, CI runs the repository contract suite against both databases.

## Alternatives considered
- **PostgreSQL from day one:** gives production parity, but Docker becomes a prerequisite for running tests and the demo, which slows M0–M5.
- **DuckDB as the operational store:** excellent for analytics, but it isn't built for transactional workflow state with concurrent writers.

## Consequences
- The demo runs with `pip install` and nothing else.
- Postgres-specific features (`jsonb` operators, `bigserial`, row-level locking) cannot be relied on before M7. Any use after M7 must stay behind the repository interfaces.
- Concurrency bugs may surface only once Postgres arrives, so RSF-076 (optional load test) and RSF-060's contract suite are the safety net.

## Revisit when
A v0.1 feature genuinely needs Postgres semantics, such as `SELECT … FOR UPDATE SKIP LOCKED` for a worker queue.
