# ADR-0002: Name the project "Systematic Research Factory"

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-005

## Context
The working title was "Autonomous Systematic Research Factory". The project's central principle is the opposite of autonomy: *prefer boring deterministic code over agent autonomy*, with the model limited to judgment steps behind human approval. The name is the first thing a reviewer reads, and "Autonomous" frames the project as another agent demo.

## Decision
The project is called **Systematic Research Factory**. Where a descriptor helps, use "governed" or "point-in-time", for example in the README tagline. The Python distribution name stays `systematic-research-factory`; the import package becomes `research_factory` (RSF-002).

## Alternatives considered
- **Keep "Autonomous":** rejected because it contradicts the design.
- **"Governed Research Factory":** accurate, but abstract.
- **"Point-in-Time Research Factory":** names the hardest problem the project solves, but is long and narrower than the full scope.

## Consequences
The MCP server's display name and the Skill descriptions drop "Autonomous". The repository folder name is unaffected.

## Revisit when
The project's scope changes materially, for example if it stops being research-only.
