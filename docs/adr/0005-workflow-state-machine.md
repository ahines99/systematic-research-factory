# ADR-0005: Keep the in-house state machine; no workflow engine

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-022, RSF-043, RSF-044, RSF-066

## Context
The spec left open whether to use Temporal or Prefect, or a small explicit state machine. Workflow engines earn their keep with durable timers, fan-out across distributed workers, long retry schedules and very large numbers of runs.

This workflow is nine sequential steps with one human pause. A human approval that takes days needs no timer: it is a `needs_review` row, and resuming is a function call.

## Decision
- Use an in-house state machine (`workflows/base.py`).
- Persist state in the operational database: `workflow_runs`, `step_results` and `audit_events`.
- Validate status transitions, persist each step result before the next step starts, and use step idempotency keys so that resuming never re-executes a completed step.

## Alternatives considered
- **Temporal:** strong guarantees, but it means running a server cluster and following replay-safety rules in workflow code. It would also hide the durability logic, which is part of what this project demonstrates.
- **Prefect:** lighter than Temporal, but still an extra service. Its strengths (scheduling, data-pipeline observability) aren't needed here.

## Consequences
- A reviewer can read the entire orchestration in a few hundred lines.
- Retries, timeouts and resume are our responsibility and must be tested (RSF-043 to RSF-047).
- There is no built-in workflow UI; the run report (RSF-049) and audit log cover that need.

## Revisit when
Any of these is needed:
- scheduled re-runs, such as monthly out-of-sample checks;
- parallel branches executed by separate workers;
- long-running retries measured in hours.

Even then, try a Postgres-backed job queue before adopting a workflow engine.
