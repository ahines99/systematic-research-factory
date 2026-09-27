# ADR-0009: Production defaults for models, spend and releases

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-039, RSF-053, RSF-071, RSF-079

## Context
The 2026-09-23 audit left four decisions to the owner. The owner accepted the recommendations below.

## Decision

**2026-09-27 amendment:** automatic paid fallback and SDK retries are disabled. Transactional reservations, bounded output, explicit refusal accounting and conservative reconciliation of uncertain calls replace the original fallback policy below. Live provider/model compatibility and billed usage remain an owner acceptance check.
1. **Default model: `claude-opus-5`** for keyed users' judgment steps (`RSF_ANTHROPIC_MODEL`). Refusals fall back server-side (`fallbacks: "default"`).
2. **Daily model-spend cap: $3.00** at first (`RSF_BUDGETS__MAX_COST_USD_PER_DAY`). Raise it deliberately once real usage is known.
3. **Guest live runs use the deterministic rules reviewer, never a paid model.** They follow the same scenario path as the recorded demo, so prior trials are frozen first and a guest cannot change a demo's outcome.
4. **No separate v0.1 release.** The local `v0.1.0` tag sat on a commit that already contained the v1.0 work, and pushing it would have triggered a production deploy. It was deleted. The first release will be `v1.0.0`.
5. **The repository is public** (a portfolio project), so CI minutes and image pulls are free.
6. **The optional load test (RSF-076) is skipped** for v1.0. The PostgreSQL concurrency test covers the contention that matters.

## Consequences
- Guests never spend model budget. The daily cap applies only to keyed users and their runs.
- A model baseline (`rsf eval --provider anthropic`) runs with Opus unless `RSF_ANTHROPIC_MODEL` says otherwise.

## Revisit when
There's real traffic, or model pricing changes.
