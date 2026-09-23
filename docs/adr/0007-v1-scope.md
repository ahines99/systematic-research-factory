# ADR-0007: Define v1.0 as a portfolio-grade production cut

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** all M6–M9 tickets

## Context
The first roadmap treated every M6–M9 ticket as required for v1.0. For a portfolio project, value per ticket drops sharply after v0.1. Dashboards, load tests and a staging environment show general operations skill that can be demonstrated more cheaply elsewhere. They add weeks of work without strengthening the project's main claim: governed, auditable, point-in-time research.

## Decision
The roadmap has three cuts:

- **v0.1 (M0–M5):** unchanged. The MVP is done well, and it carries the most weight.
- **v1.0:** v0.1 plus real EDGAR data with semi-synthetic prices, one deployed container with API-key authentication and roles, data snapshots and a reproducibility check, security testing focused on prompt injection and approval bypass, a release pipeline, and a public demo built on pre-recorded runs.
- **Optional:**
  - RSF-070: OpenTelemetry traces;
  - RSF-072: dashboards and alerts;
  - RSF-076: load test;
  - RSF-081: licensed vendor adapter;
  - RSF-083: hosted OAuth for a Claude.ai connector;
  - a staging environment.

Optional tickets are done only when a concrete need appears. Required tickets never depend on optional ones.

## Consequences
- v1.0 shrinks from about 40 to about 33 focused engineering days, and the remaining work concentrates on what differentiates the project.
- Run-level cost, latency and evidence data still exist in audit events and structured logs (RSF-041, RSF-069). Without RSF-070, they are just not exported as traces.
- "Production" in this project means *safe, reproducible, authenticated and recoverable*, not *operated at scale*.

## Revisit when
The system gains real users beyond demo visitors, or a specific optional capability becomes a goal in its own right.
