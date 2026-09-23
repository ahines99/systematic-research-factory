# Roadmap to production

Last reviewed: 2026-09-23. Ticket prefix: `RSF-`.

**Status (2026-09-23):** 69 tickets done, 10 waiting on the owner, 4 optional tickets skipped (ADR-0007). Everything that can be verified without the owner's accounts is implemented and tested; see [go-live-review.md](go-live-review.md). Status values: `done`; `owner` (code and config are complete, but the done-when needs the owner's accounts, a GitHub remote, an API key or a recording); `skipped` (optional).

This roadmap takes the repository from its current state (a spec plus a stub MCP server) to a deployed v1.0. Milestones M0–M5 match the six milestones in [IMPLEMENTATION_HANDOFF.md](../IMPLEMENTATION_HANDOFF.md) and end at the **v0.1 MVP**. Milestones M6–M9 take the MVP to **v1.0 production**. Some M6–M9 tickets are optional ([ADR-0007](adr/0007-v1-scope.md)).

## What "production" means here

This is a research system, not a trading system. v1.0 is production-ready when:

- a hosted, authenticated MCP server runs the full nine-step workflow on real SEC EDGAR filings with semi-synthetic prices ([ADR-0003](adr/0003-market-data-semi-synthetic.md));
- every run is durable, resumable, idempotent and reproducible from recorded data snapshots and code versions;
- all numbers come from deterministic, tested code, and every model judgment is schema-validated, evidence-cited and evaluated;
- approvals are enforced server-side by role, and there is no path from the system to order placement;
- structured logs, model-spend caps, backups, a runbook and a release pipeline exist and have been exercised;
- a public demo lets anyone browse pre-recorded runs without logging in, at a bounded cost.

"Production" here means safe, reproducible, authenticated and recoverable, not operated at scale. Tickets marked `optional` in the index are not required for v1.0 ([ADR-0007](adr/0007-v1-scope.md)).

**Permanently out of scope:** live trading, order routing, broker connectivity, and any irreversible action without a human approval record.

## Sizing

| Size | Meaning |
|---|---|
| `S` | Half a day or less |
| `M` | 1–2 days |
| `L` | 3–5 days |

At midpoint sizing, v0.1 is about 70 focused engineering days, the required v1.0 tickets about 33 more, and the optional tickets about 10.

## Critical path

```text
v0.1  RSF-002 → 006 → 008/009 → 016 → 017 → 018 → 020 → 023 → 026 → 032 → 038 → 039 → 042 → 048 → 053
v1.0  RSF-055 → 056 → 057 → 059 → 077 → 082 → 079 → 080
      deployment track in parallel: RSF-060 → 061 → 062 → 063 → 078 → 079
```

These can run in parallel with the critical path: CI (RSF-004), Skill content (RSF-034–037), and docs (RSF-050–051).

## Waiting on the owner

| Ticket | What's needed |
|---|---|
| RSF-004 | Push to GitHub; confirm the `ci` workflow is green; protect `main` |
| RSF-039 | Set `ANTHROPIC_API_KEY` and run `rsf eval --provider anthropic` to record the Claude baseline (the rules baseline is recorded) |
| RSF-052 | Record the demo using [demo-script.md](demo-script.md) (README claims are verified and linked) |
| RSF-060 | First CI run of the PostgreSQL job (no PostgreSQL on the build machine) |
| RSF-061 | Build the image (no Docker on the build machine): `docker compose up --build` |
| RSF-067 | Create the Fly.io, Neon and R2 resources and deploy ([deployment.md](deployment.md)) |
| RSF-068 | Run and time the restore drill ([runbook.md](runbook.md#restoring-from-backup-rsf-068)) |
| RSF-078 | Add the `FLY_API_TOKEN` secret; tag a release to exercise the pipeline |
| RSF-079 | Deploy, then `rsf demo` on the instance |
| RSF-080 | Sign off [go-live-review.md](go-live-review.md) and tag `v1.0.0` |

## Decisions

All open decisions were resolved on 2026-09-23 and recorded in [docs/adr/](adr/README.md).

| ADR | Decision | Affects |
|---|---|---|
| [0001](adr/0001-persistence-sqlite-first.md) | SQLite for v0.1, PostgreSQL (Neon) from M7 | RSF-011, 060 |
| [0002](adr/0002-project-name.md) | Project name: **Systematic Research Factory** | RSF-005 |
| [0003](adr/0003-market-data-semi-synthetic.md) | Real EDGAR filings with semi-synthetic prices; licensed vendor optional | RSF-054, 055, 057, 081 |
| [0004](adr/0004-authentication-api-keys.md) | API keys and server-side roles; read-only guest with no login; hosted OAuth only for a Claude.ai connector | RSF-062, 063, 079, 083 |
| [0005](adr/0005-workflow-state-machine.md) | In-house state machine, no workflow engine | RSF-022, 043, 066 |
| [0006](adr/0006-hosting.md) | Fly.io + Neon + Cloudflare R2; model-spend caps; pre-recorded demo runs | RSF-065, 067, 068, 071, 079, 082 |
| [0007](adr/0007-v1-scope.md) | v1.0 is a portfolio-grade cut; ops-heavy tickets are optional | M6–M9 |

## Ticket index

| ID | Title | Milestone | Cut | Size | Depends on | Status |
|---|---|---|---|---|---|---|
| RSF-001 | Initialize git repository | M0 | v0.1 | S | — | done |
| RSF-002 | Fix package layout and build system | M0 | v0.1 | S | — | done |
| RSF-003 | Dev tooling and lockfile | M0 | v0.1 | S | 002 | done |
| RSF-004 | Continuous integration | M0 | v0.1 | S | 001, 003 | owner |
| RSF-005 | ADR log and naming decision | M0 | v0.1 | S | — | done |
| RSF-006 | Core domain contracts | M0 | v0.1 | M | 002 | done |
| RSF-007 | Experiment identity and hypothesis freezing | M0 | v0.1 | S | 006 | done |
| RSF-008 | Synthetic market-data fixture | M0 | v0.1 | M | 006 | done |
| RSF-009 | Synthetic filings fixture with planted leak | M0 | v0.1 | M | 006 | done |
| RSF-010 | Golden case format and first 10 cases | M0 | v0.1 | M | 008, 009 | done |
| RSF-011 | Persistence schema and migrations | M1 | v0.1 | M | 006 | done |
| RSF-012 | Repository interfaces and in-memory fakes | M1 | v0.1 | M | 011 | done |
| RSF-013 | Content-addressed evidence store | M1 | v0.1 | M | 012 | done |
| RSF-014 | Append-only audit log | M1 | v0.1 | S | 012 | done |
| RSF-015 | Research ledger (trial counting) | M1 | v0.1 | S | 007, 012 | done |
| RSF-016 | Point-in-time data access services | M1 | v0.1 | M | 008, 009, 013 | done |
| RSF-017 | Feature build with knowledge-time lineage | M1 | v0.1 | M | 016 | done |
| RSF-018 | Backtest engine | M1 | v0.1 | L | 017 | done |
| RSF-019 | Backtest reference and property tests | M1 | v0.1 | M | 018 | done |
| RSF-020 | Leakage audit | M1 | v0.1 | M | 017, 018 | done |
| RSF-021 | Statistical review service | M1 | v0.1 | L | 015, 018 | done |
| RSF-022 | Workflow state machine | M1 | v0.1 | M | 011, 014 | done |
| RSF-023 | Primary workflow without an LLM | M1 | v0.1 | M | 013–022 | done |
| RSF-024 | CLI runner | M1 | v0.1 | S | 023 | done |
| RSF-025 | Modular MCP server layout | M2 | v0.1 | S | 002 | done |
| RSF-026 | Domain MCP tools | M2 | v0.1 | M | 023, 025 | done |
| RSF-027 | MCP resources | M2 | v0.1 | S | 026 | done |
| RSF-028 | MCP prompts | M2 | v0.1 | S | 025 | done |
| RSF-029 | Server-side policy enforcement | M2 | v0.1 | M | 026 | done |
| RSF-030 | Structured tool error model | M2 | v0.1 | S | 026 | done |
| RSF-031 | MCP integration test suite | M2 | v0.1 | M | 026–030 | done |
| RSF-032 | Evaluation harness | M3 | v0.1 | L | 010, 023 | done |
| RSF-033 | Golden dataset to 25 cases, including adversarial | M3 | v0.1 | M | 032 | done |
| RSF-034 | Skill: point-in-time-research | M3 | v0.1 | M | — | done |
| RSF-035 | Skill: financial-research-statistics | M3 | v0.1 | M | — | done |
| RSF-036 | Skill: signal-red-team | M3 | v0.1 | M | — | done |
| RSF-037 | Skill: research-committee | M3 | v0.1 | M | — | done |
| RSF-038 | Model-judgment step contract | M3 | v0.1 | M | 023 | done |
| RSF-039 | Model client and economic rationale review | M3 | v0.1 | M | 032, 038 | owner |
| RSF-040 | Implementation review and committee steps | M3 | v0.1 | M | 039 | done |
| RSF-041 | Version stamping for prompts, Skills and models | M3 | v0.1 | S | 038 | done |
| RSF-042 | Approval gates and approval records | M4 | v0.1 | M | 022, 040 | done |
| RSF-043 | Pause and resume across restarts | M4 | v0.1 | M | 042 | done |
| RSF-044 | Idempotent steps and reruns | M4 | v0.1 | M | 022 | done |
| RSF-045 | Retries and timeouts | M4 | v0.1 | S | 022 | done |
| RSF-046 | Failure-injection harness | M4 | v0.1 | M | 045 | done |
| RSF-047 | Workflow test suite | M4 | v0.1 | M | 042–046 | done |
| RSF-048 | One-command local demo | M5 | v0.1 | M | 047 | done |
| RSF-049 | Run report | M5 | v0.1 | M | 023 | done |
| RSF-050 | Architecture and data-contract docs | M5 | v0.1 | M | 031 | done |
| RSF-051 | Threat model | M5 | v0.1 | M | 029 | done |
| RSF-052 | README verification and demo recording | M5 | v0.1 | S | 048, 049 | owner |
| RSF-053 | Release v0.1.0 | M5 | v0.1 | S | 048–052 | done |
| RSF-054 | Market-data source decision | M6 | v1.0 | S | — | done |
| RSF-055 | SEC EDGAR adapter | M6 | v1.0 | L | 016 | done |
| RSF-056 | Security master and identifier history | M6 | v1.0 | M | 055 | done |
| RSF-057 | Semi-synthetic price generator for the EDGAR universe | M6 | v1.0 | L | 054, 056 | done |
| RSF-058 | Data-quality checks | M6 | v1.0 | M | 055, 057 | done |
| RSF-059 | Data snapshots for reproducibility | M6 | v1.0 | M | 055, 057 | done |
| RSF-081 | Licensed vendor price adapter | M6 | optional | L | 057 | skipped |
| RSF-060 | PostgreSQL backend | M7 | v1.0 | M | 011 | owner |
| RSF-061 | Container image and compose stack | M7 | v1.0 | M | 060 | owner |
| RSF-062 | Streamable HTTP with API-key authentication | M7 | v1.0 | M | 061 | done |
| RSF-063 | Roles and server-side authorization | M7 | v1.0 | M | 062 | done |
| RSF-064 | Secrets and configuration | M7 | v1.0 | S | 061 | done |
| RSF-065 | Object storage for evidence | M7 | v1.0 | M | 013, 061 | done |
| RSF-066 | Workflow engine decision | M7 | v1.0 | S | — | done |
| RSF-067 | Hosting and infrastructure as code | M7 | v1.0 | M | 061 | owner |
| RSF-068 | Backups and restore drill | M7 | v1.0 | S | 065, 067 | owner |
| RSF-083 | Hosted OAuth for a Claude.ai connector | M7 | optional | M | 062 | skipped |
| RSF-069 | Structured logging and redaction | M8 | v1.0 | S | 022 | done |
| RSF-070 | OpenTelemetry traces and metrics | M8 | optional | M | 069 | skipped |
| RSF-071 | Cost and latency budgets | M8 | v1.0 | S | 041, 045 | done |
| RSF-072 | Dashboards and alerts | M8 | optional | M | 070, 067 | skipped |
| RSF-073 | Operations runbook | M8 | v1.0 | S | 068, 071 | done |
| RSF-074 | Security testing | M9 | v1.0 | M | 051, 063 | done |
| RSF-075 | Supply-chain controls | M9 | v1.0 | S | 004, 061 | done |
| RSF-076 | Concurrency and load test | M9 | optional | M | 060, 062 | done |
| RSF-077 | Reproducibility audit | M9 | v1.0 | M | 059, 060 | done |
| RSF-078 | Release pipeline | M9 | v1.0 | M | 067, 075 | owner |
| RSF-079 | Public demo instance | M9 | v1.0 | M | 063, 078, 082 | owner |
| RSF-082 | Pre-recorded demo runs | M9 | v1.0 | M | 049, 059, 077 | done |
| RSF-080 | v1.0 go-live review | M9 | v1.0 | S | 073–075, 077–079, 082 | owner |

---

## M0 — Foundations, contracts and fixtures

**Goal:** a correctly packaged repository with typed contracts and deterministic fixtures whose right answers are known in advance.
**Exit criteria:** `pip install -e ".[dev]"`, then `pytest`, passes in CI; the fixtures produce the same bytes from a fixed seed; 10 golden cases are written down.

### RSF-001 · Initialize git repository
`S` · depends on: —
The project folder is not under version control.
**Done when:**
- `git init`, with a `.gitignore` for Python, `.venv`, `.env`, build output, and local data or cache folders.
- A licence is chosen and added.
- The first commit contains the current spec and scaffold.

### RSF-002 · Fix package layout and build system
`S` · depends on: —
`src/` is currently used both as a package (`from src.mcp_server import mcp`) and as a setuptools src-layout root. A wheel build installs `mcp_server`, `domain` and `workflows` as top-level modules and then fails. Tests pass only via `python -m pytest` from the repo root.
**Done when:**
- The code lives in `src/research_factory/` and imports are `research_factory.*`.
- `pyproject.toml` declares a `[build-system]` (hatchling) and the package location.
- `pip install -e ".[dev]"` succeeds in a clean venv, and a bare `pytest` passes from any working directory.

### RSF-003 · Dev tooling and lockfile
`S` · depends on: RSF-002
**Done when:**
- `.python-version` pins 3.12 and a `uv.lock` is committed.
- ruff (lint and format) and mypy (strict on `src/`) are configured and pass.
- One async test plugin is chosen: the test uses the `anyio` marker while `pytest-asyncio` is configured in `asyncio_mode = "auto"`. The other is removed.
- `pytest-cov`, and `hypothesis` for property tests, are in the dev extras.

### RSF-004 · Continuous integration
`S` · depends on: RSF-001, RSF-003
**Done when:** GitHub Actions runs ruff, mypy and pytest with coverage on Python 3.12 and 3.13 for every push and pull request, and the main branch requires CI to pass.

### RSF-005 · ADR log and naming decision
`S` · depends on: — · **done 2026-09-23**
Architecture decisions should be recorded, not rediscovered.
**Done when:**
- ✅ `docs/adr/` exists with a template and an index.
- ✅ ADR-0001 to ADR-0007 record persistence, name, market data, authentication, workflow engine, hosting and v1.0 scope.
- ✅ The rename to "Systematic Research Factory" is applied to the MCP server display name and the Skill descriptions.

### RSF-006 · Core domain contracts
`M` · depends on: RSF-002
**Done when:**
- `models.py` gains `AuditEvent`, which the spec defines but the code lacks.
- `project_models.py` defines `Hypothesis`, `BacktestSpec`, `ExperimentId`, `RunStatus`, `StepResult` and `ApprovalRecord`.
- Every contract carries a `schema_version`. Frozen artifacts use `model_config = ConfigDict(frozen=True)`.
- Validators reject timezone-naive datetimes, `horizon_days <= 0`, negative costs and negative execution delay.
- Unit tests cover every validator.

### RSF-007 · Experiment identity and hypothesis freezing
`S` · depends on: RSF-006
Enforces the rule "no hypothesis mutation without a new experiment ID".
**Done when:**
- `experiment_id` is a stable content hash of the canonical JSON of the frozen hypothesis and backtest spec.
- Any field change produces a new ID.
- There is no API that modifies a frozen hypothesis in place, and a test proves it.

### RSF-008 · Synthetic market-data fixture
`M` · depends on: RSF-006
A seeded generator of daily prices for about 50 tickers over about 5 years. It includes delistings, splits, a ticker reused by a different company, and a **planted signal with a known true information coefficient**, so tests know the right answer.
**Done when:** the same seed produces the same output (checked by hash), and a README next to the generator documents the planted effects.

### RSF-009 · Synthetic filings fixture with planted leak
`M` · depends on: RSF-006
Filings with `period_end`, `filed_at` and `accepted_at` timestamps, including restatements. One feature variant deliberately uses `period_end` instead of acceptance time, which is a classic look-ahead leak.
**Done when:** fixtures are deterministic, and the leaky variant is labelled in fixture metadata so the leakage audit can be scored.

### RSF-010 · Golden case format and first 10 cases
`M` · depends on: RSF-008, RSF-009
**Done when:**
- A YAML case schema covers input hypothesis and spec, expected step outcomes, expected findings or errors, and required evidence IDs.
- The first 10 cases include:
  - a clean pass
  - a planted leak that is caught
  - an overfit, many-trial signal that fails the deflated Sharpe ratio
  - a missing `as_of` that is rejected
  - an attempt to change a frozen hypothesis that is rejected
  - a delisted-stock survivorship trap
  - a restatement trap
  - zero signal
  - costs that erase the edge
  - an execution-delay-sensitive signal

---

## M1 — Deterministic core

**Goal:** the complete nine-step workflow runs on fixtures with **no LLM**. It persists runs, evidence, findings and audit events.
**Exit criteria:** `rsf run` on the clean golden case completes, and on the leak case it fails at the leakage audit. Both runs leave a complete audit trail.

### RSF-011 · Persistence schema and migrations
`M` · depends on: RSF-006
**Done when:**
- SQLAlchemy 2 models and Alembic migrations exist for `workflow_runs`, `evidence`, `findings`, `finding_evidence`, `audit_events`, `experiments`, `step_results` and `approvals`.
- Migrations run on SQLite now and on Postgres unchanged from RSF-060 (portable types only).

### RSF-012 · Repository interfaces and in-memory fakes
`M` · depends on: RSF-011
**Done when:** each aggregate has a `Protocol` repository, a SQL implementation and an in-memory fake, and the same contract test suite runs against both implementations.
*As built:* the in-memory implementation is the same SQL code on in-memory SQLite, so there is no second implementation to drift; the contract suite runs on SQLite locally and on PostgreSQL in CI.

### RSF-013 · Content-addressed evidence store
`M` · depends on: RSF-012
**Done when:**
- Blobs are stored by SHA-256, and originals are immutable, with derived text stored separately.
- Every evidence record has a `source_uri`, `source_type`, `as_of` and `content_hash`.
- Storing the same bytes twice returns the same ID.

### RSF-014 · Append-only audit log
`S` · depends on: RSF-012
**Done when:** every service call writes an `AuditEvent` with actor, step and payload hash; there is no update or delete path in code; and a test asserts that events are only ever appended.

### RSF-015 · Research ledger (trial counting)
`S` · depends on: RSF-007, RSF-012
The deflated Sharpe ratio and any multiple-testing correction need an honest count of trials.
**Done when:** each experiment is recorded under a research family, the trial count per family can be queried, and ledger rows are immutable.

### RSF-016 · Point-in-time data access services
`M` · depends on: RSF-008, RSF-009, RSF-013
**Done when:**
- `get_prices_as_of` and `get_filings_as_of` require a timezone-aware `as_of`.
- They never return a row whose knowledge time is later than `as_of`, and the universe reflects membership as of that date, including later-delisted names.
- Every read is recorded as evidence.

### RSF-017 · Feature build with knowledge-time lineage
`M` · depends on: RSF-016
**Done when:** every feature value carries the latest knowledge timestamp of its inputs and the evidence IDs it was built from. Features are computed with Polars and are deterministic.

### RSF-018 · Backtest engine
`L` · depends on: RSF-017
A vectorised backtester that applies:
- execution delay
- transaction costs in basis points
- holding period
- a point-in-time universe
- corporate-action-adjusted returns

**Done when:** it returns daily returns, positions and turnover as a structured artifact with an evidence ID, and identical inputs give identical outputs.

### RSF-019 · Backtest reference and property tests
`M` · depends on: RSF-018
**Done when:**
- Small hand-computed fixtures match to 1e-12.
- Property tests show that a zero signal gives roughly minus costs, higher costs never raise net returns, and a one-day extra delay on the planted signal lowers the information coefficient.
- The planted-signal information coefficient is recovered within tolerance.

### RSF-020 · Leakage audit
`M` · depends on: RSF-017, RSF-018
**Done when:**
- The audit checks that feature knowledge time is at or before decision time, that the execution delay was applied, that universe membership is as of the decision date, and that the target is not among the features.
- It catches RSF-009's planted leak and passes the clean variant.
- It produces findings with evidence links.

### RSF-021 · Statistical review service
`L` · depends on: RSF-015, RSF-018
**Done when:**
- It computes Sharpe ratio, Newey-West t-statistic, bootstrap confidence intervals, information coefficient and its ratio to its volatility, and the deflated Sharpe ratio using the ledger's trial count.
- Each statistic is checked against a reference implementation or published worked example.
- Thresholds are configuration, not code.

### RSF-022 · Workflow state machine
`M` · depends on: RSF-011, RSF-014
Implements `workflows/base.py` from the spec, with persistence.
**Done when:** status transitions are validated (no `complete` → `running`), each step result is persisted before the next step starts, and every transition writes an audit event.

### RSF-023 · Primary workflow without an LLM
`M` · depends on: RSF-013 to RSF-022
**Done when:**
- All nine steps are wired.
- The three judgment steps (economic rationale, implementation review, committee) use deterministic placeholders that return `NEEDS_REVIEW`.
- The clean golden case reaches the committee, and the leak case fails at the leakage audit.

### RSF-024 · CLI runner
`S` · depends on: RSF-023
**Done when:** `rsf run --hypothesis <file>` runs the workflow, and `rsf show <run_id>` prints status, step artifacts and the audit trail.

---

## M2 — MCP surface

**Goal:** a narrow, typed MCP interface over the deterministic core, with policies enforced on the server.
**Exit criteria:** every tool has in-process integration tests for success and failure, and forbidden actions fail closed.

### RSF-025 · Modular MCP server layout
`S` · depends on: RSF-002
**Done when:** the server is split into modules for `sec_pit`, `market_data_pit`, `factor_research`, `backtest` and `research_ledger`, and one process mounts them. The boundaries are documented so any module can later become its own server.

### RSF-026 · Domain MCP tools
`M` · depends on: RSF-023, RSF-025
**Done when:**
- These tools exist, with Pydantic input and output models: `freeze_hypothesis`, `get_filing_as_of`, `get_prices_as_of`, `run_backtest`, `audit_leakage`, `start_run` and `get_run_report`.
- Each is a thin wrapper over a service, with no business logic in the tool.

### RSF-027 · MCP resources
`S` · depends on: RSF-026
**Done when:** `project://policies` returns structured policy data (today it returns a single pipe-delimited string), and `run://{run_id}`, `evidence://{evidence_id}` and `ledger://{family}` exist.

### RSF-028 · MCP prompts
`S` · depends on: RSF-025
**Done when:** the spec's `review_run` prompt is implemented (it is missing today), and a `red_team_signal` prompt is added.

### RSF-029 · Server-side policy enforcement
`M` · depends on: RSF-026
**Done when:**
- `policies.py` implements `check_action`.
- A missing `as_of`, changes to frozen hypotheses and unapproved high-risk actions are rejected in code, not by prompt.
- No trading or order tool exists, and a test asserts that the tool list contains none.

### RSF-030 · Structured tool error model
`S` · depends on: RSF-026
**Done when:** errors come back as typed results with codes (`AS_OF_REQUIRED`, `HYPOTHESIS_FROZEN`, `NEEDS_EVIDENCE`, `APPROVAL_REQUIRED`, `UPSTREAM_UNAVAILABLE`), and no stack traces or internal paths leak to the client.

### RSF-031 · MCP integration test suite
`M` · depends on: RSF-026 to RSF-030
**Done when:**
- Every tool, resource and prompt has an in-process `Client` test for success and failure.
- The healthcheck test asserts `structured_content["status"] == "ok"`; today it only checks `is_error`.

---

## M3 — Skills, model reasoning and evaluation

**Goal:** the model appears only at judgment steps, and each of those steps is evaluated. Evaluation is built before prompts are tuned.
**Exit criteria:** 25 golden cases score on all seven evaluation dimensions, and all four Skills contain domain-specific procedure.

### RSF-032 · Evaluation harness
`L` · depends on: RSF-010, RSF-023
**Done when:**
- Golden cases run and are scored on the seven dimensions in the spec: tool correctness, evidence fidelity, calculation fidelity, permission fidelity, uncertainty calibration, recovery, and cost and latency.
- It writes a scorecard file.
- Deterministic cases run in CI; model cases run on demand or nightly with a pinned model ID.

### RSF-033 · Golden dataset to 25 cases, including adversarial
`M` · depends on: RSF-032
**Done when:** there are at least 25 cases, including prompt injection embedded in filing text, stale data, duplicate entities, contradictory evidence and missing required fields.

### RSF-034 · Skill: point-in-time-research
`M` · depends on: —
The four current Skills are the same boilerplate with only the name changed. That fails the spec's check that "at least one Skill is dynamically useful and not just duplicate prompt text".
**Done when:**
- The Skill has a specific trigger description.
- Its procedure covers EDGAR acceptance time versus filing date versus period end, restatements, survivorship and delistings, ticker reuse, corporate actions, and time-zone and trading-calendar alignment.
- `references/` holds deeper notes, and `scripts/` holds a timestamp-check helper.
- A golden case shows the Skill changing an outcome.

### RSF-035 · Skill: financial-research-statistics
`M` · depends on: —
**Done when:** it covers multiple testing and the t-greater-than-3 rule of thumb, the deflated Sharpe ratio, serial correlation and Newey-West, when not to trust a Sharpe ratio, and decision thresholds that point to RSF-021's configuration. All arithmetic is sent to tools.

### RSF-036 · Skill: signal-red-team
`M` · depends on: —
**Done when:**
- It gives an attack checklist: leakage, data snooping, regime dependence, crowding, capacity, cost sensitivity, and dependence on a small number of names.
- It defines a required output format: attack, evidence, severity, and whether the attack was refuted.

### RSF-037 · Skill: research-committee
`M` · depends on: —
**Done when:** it has a decision rubric (approve, reject, or needs more evidence), a memo template that separates facts, assumptions and recommendations, a way to record dissent, and a rule that every material claim cites an evidence ID.

### RSF-038 · Model-judgment step contract
`M` · depends on: RSF-023
**Done when:**
- Judgment steps receive only structured artifacts and return schema-validated Pydantic output.
- Output citing an evidence ID that doesn't exist is rejected.
- Insufficient evidence becomes `NEEDS_EVIDENCE`.
- Each step documents why a deterministic rule is not enough, as the spec requires.

### RSF-039 · Model client and economic rationale review
`M` · depends on: RSF-032, RSF-038
**Done when:**
- A `ModelClient` interface has an Anthropic SDK implementation and a deterministic fake.
- The economic rationale review uses it.
- The model ID, prompt version, tokens, cost and latency are recorded.
- Evaluation scores are recorded as a baseline.

### RSF-040 · Implementation review and committee steps
`M` · depends on: RSF-039
**Done when:**
- Implementation review assesses capacity, turnover and cost realism from backtest artifacts.
- The committee step produces the RSF-037 memo.
- Both are evaluated.

### RSF-041 · Version stamping for prompts, Skills and models
`S` · depends on: RSF-038
**Done when:** every model-driven audit event records the prompt hash, Skill version, model ID and input and output schema versions.

---

## M4 — Approvals and recovery

**Goal:** the workflow stops at human boundaries and survives failures.
**Exit criteria:** a run pauses at the committee, resumes after a process restart, and survives one injected tool failure.

### RSF-042 · Approval gates and approval records
`M` · depends on: RSF-022, RSF-040
**Done when:**
- The workflow enters `needs_review` at the committee and at any policy-flagged action.
- An `ApprovalRecord` (approver, time, decision, reason) is required to continue.
- Rejections end the run, and the rejection is recorded.

### RSF-043 · Pause and resume across restarts
`M` · depends on: RSF-042
**Done when:** a paused or interrupted run resumes from persisted state in a new process without re-executing completed steps.

### RSF-044 · Idempotent steps and reruns
`M` · depends on: RSF-022
**Done when:** each step has an idempotency key of experiment ID plus step plus input hash; re-execution returns the stored artifact; and the same experiment ID always gives identical artifacts.

### RSF-045 · Retries and timeouts
`S` · depends on: RSF-022
**Done when:** each step has a timeout and a retry policy with backoff for transient errors, validation and policy errors are never retried, and every retry is audited.

### RSF-046 · Failure-injection harness
`M` · depends on: RSF-045
**Done when:** tests can inject a tool timeout, malformed source data or a partial source outage, and each produces controlled, audited behaviour rather than a crash.

### RSF-047 · Workflow test suite
`M` · depends on: RSF-042 to RSF-046
**Done when:** `tests/test_workflow.py` covers pause and resume, idempotent reruns, provenance links, approval rejection and at least one injected dependency failure.

---

## M5 — v0.1 MVP demo and portfolio polish

**Goal:** a stranger can clone the repo, run one command, and see both the success path and a controlled failure path.
**Exit criteria:** every item in the spec's acceptance checklist is ticked; v0.1.0 is tagged.

### RSF-048 · One-command local demo
`M` · depends on: RSF-047
**Done when:** `make demo` (or `uv run rsf demo`) seeds fixtures and runs the clean case to an approval pause and the leak case to a controlled failure, printing both reports.

### RSF-049 · Run report
`M` · depends on: RSF-023
**Done when:** a Markdown or HTML report per run shows the hypothesis, each step's artifact, findings with evidence links, approvals and the audit timeline.

### RSF-050 · Architecture and data-contract docs
`M` · depends on: RSF-031
**Done when:** `docs/architecture.md` has a diagram matching the code, and `docs/data_contracts.md` is generated from the Pydantic schemas.

### RSF-051 · Threat model
`M` · depends on: RSF-029
**Done when:** `docs/threat_model.md` covers prompt injection through retrieved filings, data poisoning, over-broad tool access, approval bypass, secret exposure and fetching of attacker-supplied source URIs (SSRF), with each mitigation mapped to a test.

### RSF-052 · README verification and demo recording
`S` · depends on: RSF-048, RSF-049
**Done when:** every claim in the README's "Why this is not just a chatbot" section links to code or a test, and the 3-minute demo script and recording are done.

### RSF-053 · Release v0.1.0
`S` · depends on: RSF-048 to RSF-052
**Done when:** the acceptance checklist in the handoff is fully ticked, a changelog exists, and the `v0.1.0` tag is pushed.

---

## M6 — Real data

**Goal:** run on real, point-in-time public filings without weakening any guarantee or losing the known right answer.
**Exit criteria:** the workflow runs on real EDGAR filings with semi-synthetic prices, with data-quality gates and replayable snapshots.

### RSF-054 · Market-data source decision
`S` · depends on: — · **done 2026-09-23**
**Done when:** ✅ [ADR-0003](adr/0003-market-data-semi-synthetic.md) records the choice: real EDGAR filings, semi-synthetic prices keyed to acceptance time, fully synthetic fixtures for tests, and an optional licensed vendor adapter (RSF-081).

### RSF-055 · SEC EDGAR adapter
`L` · depends on: RSF-016
**Done when:**
- It uses the `submissions` and `companyfacts` APIs, with acceptance time treated as knowledge time.
- It sends a declared `User-Agent` and stays under SEC's request-rate limit.
- It has a local cache keyed by content hash, and contract tests run against recorded responses.

### RSF-056 · Security master and identifier history
`M` · depends on: RSF-055
**Done when:** the CIK ↔ ticker mapping is resolved as of a date (tickers get reused), and a lookup never resolves through a mapping that became effective later.

### RSF-057 · Semi-synthetic price generator for the EDGAR universe
`L` · depends on: RSF-054, RSF-056
Implements the price side of [ADR-0003](adr/0003-market-data-semi-synthetic.md).
**Done when:**
- Daily prices are simulated for the real EDGAR company universe, keyed by CIK, from a fixed seed.
- Returns embed a planted relationship of documented strength with a filing-derived feature, keyed to **acceptance time**.
- Companies that stopped filing are delisted in the simulation, so the universe is survivorship-safe.
- A test shows that building the feature from period-end dates instead of acceptance times inflates the measured information coefficient by a known amount, and the leakage audit flags it.
- It sits behind the same interface as the fixture adapter and passes the same contract tests.
- Every report and demo screen labels prices as simulated.

### RSF-058 · Data-quality checks
`M` · depends on: RSF-055, RSF-057
**Done when:** stale data, gaps, duplicates and outliers produce flagged evidence, and failed checks move the run to `NEEDS_EVIDENCE` instead of producing a silent result.

### RSF-059 · Data snapshots for reproducibility
`M` · depends on: RSF-055, RSF-057
**Done when:** each run records the snapshot IDs of every dataset it read, and archived snapshots can be replayed exactly.

### RSF-081 · Licensed vendor price adapter
`L` · depends on: RSF-057 · optional
**Done when:** a licensed survivorship-free vendor is available behind the same price interface for private research. Configuration keeps vendor data out of the repository, fixtures and public demo, and a CI check enforces this.

---

## M7 — Persistence and deployment

**Goal:** a hosted, authenticated, recoverable service.
**Exit criteria:** the production deployment runs the demo over Streamable HTTP with API-key authentication, and a restore from backup has been rehearsed.

### RSF-060 · PostgreSQL backend
`M` · depends on: RSF-011
**Done when:** migrations and the repository contract suite run against Postgres in CI (testcontainers), SQLite remains the zero-setup developer default, and the deployed database is Neon ([ADR-0006](adr/0006-hosting.md)).

### RSF-061 · Container image and compose stack
`M` · depends on: RSF-060
**Done when:** a multi-stage Dockerfile builds an image that runs as a non-root user with pinned dependencies, and `docker-compose.yml` starts the app and Postgres (plus an OpenTelemetry collector if RSF-070 is done).

### RSF-062 · Streamable HTTP with API-key authentication
`M` · depends on: RSF-061
Implements [ADR-0004](adr/0004-authentication-api-keys.md).
**Done when:**
- The MCP server runs over Streamable HTTP behind an ASGI app with TLS terminated at the platform proxy.
- Bearer API keys are random, shown once, stored only as hashes, revocable, and issued through the CLI.
- Requests without a valid key are rejected, except the read-only guest routes defined in RSF-079.

### RSF-063 · Roles and server-side authorization
`M` · depends on: RSF-062
**Done when:**
- `researcher`, `approver` and `viewer` roles exist, plus an unauthenticated `guest` role that can only read pre-recorded runs.
- Only approvers can write approval records, and the approver can't be the run requester for committee decisions.
- Everything is enforced on the server and tested.

### RSF-064 · Secrets and configuration
`S` · depends on: RSF-061
**Done when:** `.env.example` exists, a typed settings class loads configuration, secrets come from the environment or a secret store, and a CI check fails if secrets appear in Skills, prompts or logs.

### RSF-065 · Object storage for evidence
`M` · depends on: RSF-013, RSF-061
**Done when:** evidence blobs go to Cloudflare R2 through the S3-compatible API; the app's credentials cannot delete or overwrite objects (confirm R2's bucket lock or retention options); and the local filesystem backend stays available for development.

### RSF-066 · Workflow engine decision
`S` · depends on: — · **done 2026-09-23**
**Done when:** ✅ [ADR-0005](adr/0005-workflow-state-machine.md) records the decision to keep the in-house state machine. Check its revisit triggers at the end of M4.

### RSF-067 · Hosting and infrastructure as code
`M` · depends on: RSF-061
**Done when:** production runs on Fly.io with Neon and R2 per [ADR-0006](adr/0006-hosting.md); `fly.toml` and environment documentation are committed; and idle hosting cost is measured at about $25 a month or less. A separate staging environment is optional.

### RSF-068 · Backups and restore drill
`S` · depends on: RSF-065, RSF-067
**Done when:** Neon's point-in-time restore window is confirmed for the chosen plan, evidence is write-once in R2, and one documented restore into a scratch database has been performed and timed.

### RSF-083 · Hosted OAuth for a Claude.ai connector
`M` · depends on: RSF-062 · optional
**Done when:** a hosted identity provider issues tokens, the server validates them alongside API keys and maps them to roles, and the server works as a Claude.ai custom connector. No authorization server is built in-house. First confirm which authentication modes Claude.ai connectors currently support.

---

## M8 — Observability and operations

**Goal:** every run can be explained after the fact, and problems page someone.
**Exit criteria:** every field in the spec's "Every run should emit" list is recorded in audit events or structured logs, model-spend caps are enforced, and the runbook has been rehearsed. Traces and dashboards (RSF-070, RSF-072) are optional.

### RSF-069 · Structured logging and redaction
`S` · depends on: RSF-022
**Done when:** structlog JSON logs carry `run_id`, `step` and `tool_name`, a redaction filter covers secrets and raw payloads (hashes and IDs only), and a test confirms the redaction.

### RSF-070 · OpenTelemetry traces and metrics
`M` · depends on: RSF-069 · optional
**Done when:**
- Each run is a trace and each step and tool call is a span.
- Attributes include model, latency, token and cost estimate, schema versions, evidence IDs read, approval events and retries.
- The trace records whether a human changed the recommendation.

### RSF-071 · Cost and latency budgets
`S` · depends on: RSF-041, RSF-045
**Done when:** per-run token and cost budgets, a global daily model-spend cap and a latency target are configured; exceeding a budget pauses the run with an audit event; and hitting the daily cap disables live runs until the next day ([ADR-0006](adr/0006-hosting.md)).

### RSF-072 · Dashboards and alerts
`M` · depends on: RSF-067, RSF-070 · optional
**Done when:** dashboards show run outcomes, step failure rates, cost per run and approval latency, and alerts fire on error-rate and budget breaches.

### RSF-073 · Operations runbook
`S` · depends on: RSF-068, RSF-071
**Done when:** `docs/runbook.md` covers replaying a run, resuming a stuck run, rotating keys, restoring from backup, handling a source outage, a model-provider outage (judgment steps pause; deterministic steps continue), and hitting the daily model-spend cap.

---

## M9 — Hardening and v1.0 release

**Goal:** confidence that the system is safe, reproducible and releasable.
**Exit criteria:** the go-live review is signed off.

### RSF-074 · Security testing
`M` · depends on: RSF-051, RSF-063
**Done when:** there are automated tests for prompt injection (a corpus of filing text with embedded instructions), approval bypass, authentication bypass, cross-role access and fetching of attacker-supplied source URIs, and every threat-model item has a passing test.

### RSF-075 · Supply-chain controls
`S` · depends on: RSF-004, RSF-061
**Done when:** `pip-audit` and container image scanning run in CI, an SBOM is published with each release, and base images and dependencies are pinned.

### RSF-076 · Concurrency and load test
`M` · depends on: RSF-060, RSF-062 · optional
**Done when:** N concurrent runs complete without database contention errors or cross-run data mixing; throughput and p95 latency are recorded.

### RSF-077 · Reproducibility audit
`M` · depends on: RSF-059, RSF-060
**Done when:** a run archived from an earlier release is replayed from its snapshots and recorded code version and gives byte-identical deterministic artifacts, and this check runs in CI against a stored archive.

### RSF-078 · Release pipeline
`M` · depends on: RSF-067, RSF-075
**Done when:** releases use semantic versioning with a changelog, a tagged release builds and publishes the container image, migrations run on deploy, and a rollback procedure is documented and tested once. A staging step is optional.

### RSF-079 · Public demo instance
`M` · depends on: RSF-063, RSF-078, RSF-082
**Done when:**
- Guests can browse pre-recorded runs without logging in.
- Live guest runs are rate-limited to a small daily number and stop when the daily model-spend cap is reached.
- The demo labels prices as simulated.

### RSF-082 · Pre-recorded demo runs
`M` · depends on: RSF-049, RSF-059, RSF-077
**Done when:** a curated library of completed runs (clean pass, leak caught, overfit rejected, committee approval and rejection) is stored with its snapshots; guests can open each run's report and audit trail; and a CI check replays each run to confirm it is still byte-identical.

### RSF-080 · v1.0 go-live review
`S` · depends on: RSF-073 to RSF-075, RSF-077 to RSF-079, RSF-082
**Done when:** the "What production means here" criteria at the top of this file are each checked against evidence, open risks are recorded, and `v1.0.0` is tagged.
