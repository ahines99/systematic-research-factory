# 02. Systematic Research Factory

## Implementation-agent handoff

> Formerly "Autonomous Systematic Research Factory". It was renamed because the design deliberately limits autonomy ([ADR-0002](docs/adr/0002-project-name.md)). Architecture decisions are recorded in [docs/adr/](docs/adr/README.md). Where an ADR and this document disagree, the ADR wins.

### Mission
Run systematic equity research that is point-in-time clean and auditable, from a frozen hypothesis through robustness testing and research-committee review. The system exists to prevent the usual ways quant research fails:

| Failure mode | Guard |
|---|---|
| Look-ahead bias | Every data query requires `as_of`; the leakage audit checks each feature's knowledge time against its decision time |
| Survivorship bias | The universe is resolved as of the decision date, including names that later delisted |
| P-hacking and goalpost moving | Hypotheses are frozen; any change creates a new experiment ID; the research ledger counts every trial |
| Overfitting | Deflated Sharpe ratio using the ledger's trial count; multiple-testing-aware thresholds |
| LLM arithmetic errors | All returns and statistics come from deterministic, tested services |
| Unsupported conclusions | Every finding cites evidence IDs, or returns `NEEDS_EVIDENCE` |
| Unreviewed action | Human approval boundaries; no trading capability exists |

### Definition of done (v0.1 MVP)
A credible MVP is not a chat demo. It must:
- expose typed MCP capabilities;
- persist workflow state;
- preserve evidence and provenance;
- stop at approval boundaries;
- include at least one Agent Skill with real domain content;
- ship with integration tests.

The demonstration shows a complete end-to-end run with both a successful path and a controlled failure or review path. Production (v1.0) criteria are defined in [docs/ROADMAP.md](docs/ROADMAP.md#what-production-means-here).

### Non-goals
- No autonomous irreversible actions. Live trading, order routing and broker connectivity are out of scope permanently, not just for v0.1.
- The LLM is not the system of record.
- Deterministic calculations are not hidden inside prompts.
- No generalized multi-agent framework before the primary workflow works.
- No UI optimization before evidence, contracts and tests are stable.


## Current state (as of 2026-09-23)

**v0.1 is complete, and v1.0 is implemented and verified locally.** Deployment waits on the owner's accounts; see [docs/go-live-review.md](docs/go-live-review.md) and the ticket statuses in [docs/ROADMAP.md](docs/ROADMAP.md#ticket-index).

| Area | State |
|---|---|
| Package | `src/research_factory`, built with hatchling, locked with `uv.lock`; Python 3.12+ |
| Quality gates | ruff, `ruff format`, strict mypy, 152 pytest tests (on 3.12 and 3.14), 28 golden eval cases |
| Data | Synthetic worlds with planted effects, plus real SEC EDGAR filings for 44 companies with simulated prices |
| Workflow | All nine steps, persisted, resumable, idempotent, with retries, timeouts, fault injection and approvals |
| MCP | 15 tools, 4 resources, 2 prompts over stdio or Streamable HTTP with API keys and roles |
| Skills | Four Skills with procedures, references and a timestamp-check script, loaded into the judgment prompts |
| Docs | Architecture, data contracts (generated), threat model, deployment, runbook, go-live review, ADRs |
| Not yet done | GitHub CI run, container build, Fly.io/Neon/R2 deployment, restore drill, demo recording, a Claude eval baseline (needs an API key) |

The code sketches in earlier versions of this document were the design; the implementation is now authoritative. The [implementation map](#implementation-map) below points to it.


## Reference architecture

Use a four-layer design:

1. **Data and capability layer**: source systems, deterministic calculation services, document and evidence stores, and domain APIs.
2. **MCP boundary**: small servers that expose typed tools, resources and user-selectable prompts. MCP is the capability contract, not the business-logic layer.
3. **Skill layer**: Agent Skills package procedural knowledge, review checklists, reference material and scripts. A Skill teaches *how to do the work*; it is not a hidden database or a hard-coded workflow engine.
4. **Workflow and orchestration layer**: a state machine or durable workflow service coordinates steps, approvals, retries, parallel branches and audit events.

**Why this split**
- Deterministic services own arithmetic, portfolio math, joins, permissions and irreversible side effects.
- MCP gives the model a standardized, inspectable capability surface.
- Skills keep domain operating procedures version-controlled and progressively disclosed.
- The workflow engine owns state and recovery, so the LLM conversation never becomes the source of truth.

For local development, use MCP over stdio or in-process tests. For deployed servers, use Streamable HTTP behind authenticated ASGI infrastructure. Use the MCP Python SDK v2; 2.2.0 is installed and verified. Target Python 3.12+; 3.14 also works locally.


## Recommended stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | Pinned via `.python-version` (RSF-003) |
| Environment | `uv` with committed `uv.lock` | `uv sync --locked` |
| Build backend | hatchling | Skills are bundled into the wheel |
| MCP | `mcp[cli]` v2 | `MCPServer`, in-process `Client` |
| Contracts | Pydantic v2 | Frozen models for frozen artifacts |
| Operational state | **SQLite for v0.1**, PostgreSQL from M7 | SQLAlchemy 2 + Alembic with portable types only (ADR-0001, RSF-060) |
| Analytics | NumPy | Dense in-memory matrices; deterministic (see deviations below) |
| Evidence blobs | Local content-addressed store, then S3-compatible storage with object lock | RSF-013, RSF-065 |
| Workflow | In-house state machine persisted in the operational DB; no workflow engine | [ADR-0005](docs/adr/0005-workflow-state-machine.md) |
| Market data | Real SEC EDGAR filings; semi-synthetic prices keyed to acceptance time; fully synthetic fixtures for tests | [ADR-0003](docs/adr/0003-market-data-semi-synthetic.md) |
| Model access | Anthropic SDK (`claude-opus-5`, structured output, refusal fallback) behind a `JudgmentProvider` interface | Deterministic rules provider for offline use and tests (RSF-039) |
| Observability | structlog; OpenTelemetry optional | RSF-069; RSF-070 optional ([ADR-0007](docs/adr/0007-v1-scope.md)) |
| Tests | pytest with `anyio`, in-process MCP client, Starlette test client, `hypothesis` for property tests | Warnings are errors for this package |
| Authentication | Bearer API keys with server-side roles; read-only guest with no login; hosted OAuth only if a Claude.ai connector is wanted | [ADR-0004](docs/adr/0004-authentication-api-keys.md) |
| Deployment | Docker, ASGI (Starlette/FastAPI only for non-MCP endpoints) on Fly.io, with Neon Postgres and Cloudflare R2 | [ADR-0006](docs/adr/0006-hosting.md) |

Not used by default: pgvector (no semantic-retrieval need yet), Neo4j (not graph-heavy), dbt (no warehouse).

Keep the agent framework out of the center of the repository. Put orchestration behind interfaces so Claude, another model or a deterministic job can drive the same domain services.


## Project architecture

### MCP capability boundaries
In the MVP these are separate modules in one process (RSF-025). Split them into separate servers only when authorization, lifecycle or deployment needs diverge.

| Module | Responsibility | Example tools |
|---|---|---|
| `sec_pit` | Filings and XBRL facts as known at `as_of`, using SEC acceptance time as knowledge time; restatement-aware | `get_filings_as_of` |
| `market_data_pit` | Prices, corporate actions and universe membership as known at `as_of`; survivorship-safe | `get_prices_as_of`, `get_universe_as_of` |
| `factor_research` | Feature build with knowledge-time lineage; leakage audit | `build_features`, `audit_leakage` |
| `backtest` | Deterministic backtests and statistical review | `run_backtest`, `get_statistics` |
| `research_ledger` | Hypothesis freezing, experiment identity, trial counting, runs, evidence, approvals | `freeze_hypothesis`, `start_run`, `resume_run`, `get_run_report`, `list_runs`, `approve_run`, `get_ledger` |

### Agent Skills
Skills hold checklists, decision rules, examples and reference links. They never hold secrets or mutable state. The frontmatter advertises the Skill, the body gives the procedure, and `references/` or `scripts/` add depth only when needed.

| Skill | Must contain (currently placeholder) |
|---|---|
| `point-in-time-research` | Acceptance time vs. filing date vs. period end; restatements; survivorship and delistings; ticker reuse; corporate actions; calendar and time-zone alignment; a timestamp-check script (RSF-034) |
| `financial-research-statistics` | Multiple testing; deflated Sharpe ratio; Newey-West; when not to trust a Sharpe ratio; decision thresholds tied to service config (RSF-035) |
| `signal-red-team` | Attack checklist (leakage, data snooping, regime dependence, crowding, capacity, cost sensitivity, dependence on a few names) and required output format (RSF-036) |
| `research-committee` | Approve / reject / needs-more-evidence rubric; memo template separating facts, assumptions and recommendations; dissent recording (RSF-037) |

### Primary workflow

| # | Step | Executor | Deterministic artifact | Controlled failure path |
|---|---|---|---|---|
| 1 | Hypothesis freeze | Deterministic | Frozen `Hypothesis` + `experiment_id` + ledger entry | Invalid spec; attempt to change a frozen hypothesis |
| 2 | Data acquisition | Deterministic | Evidence records for every point-in-time read | Missing `as_of`; source outage; data-quality failure → `NEEDS_EVIDENCE` |
| 3 | Feature build | Deterministic | Feature table with knowledge-time lineage | Malformed source data |
| 4 | Backtest | Deterministic | Returns, positions and turnover artifact | Degenerate universe; timeout |
| 5 | Leakage audit | Deterministic | Leakage findings with evidence links | Leak detected → run fails |
| 6 | Statistical review | Deterministic | Sharpe, Newey-West t-stat, bootstrap CI, deflated Sharpe ratio | Below thresholds → flagged finding |
| 7 | Economic rationale review | Model judgment | Schema-validated rationale citing evidence IDs | Uncited claims rejected; `NEEDS_EVIDENCE` |
| 8 | Implementation review | Model judgment over deterministic inputs | Capacity, turnover and cost assessment | Unrealistic costs flagged |
| 9 | Research committee | Model-drafted memo + **human approval** | Committee memo + `ApprovalRecord` | Pauses at `needs_review`; rejection recorded |

### Human approval boundaries
- No live trading, in the MVP or later.
- No hypothesis mutation without a new experiment ID.
- Every market or filing query requires `as_of`.
- No LLM calculation of returns or statistics.
- The committee decision requires an approver who is not the run requester (enforced from RSF-063).

## Implementation map

| Concern | Code | Docs |
|---|---|---|
| Contracts | `domain/models.py`, `domain/project_models.py`, `judgment/contract.py` | [data_contracts.md](docs/data_contracts.md) (generated) |
| Experiment identity and ledger | `domain/identity.py`, `services/ledger.py` | ADR-0001 |
| Persistence | `persistence/schema.py`, `persistence/migrations/`, `persistence/repositories.py`, `persistence/blobs.py` | [data_contracts.md](docs/data_contracts.md#relational-schema) |
| Evidence and audit | `services/evidence.py`, `services/audit.py` | [architecture.md](docs/architecture.md#evidence-and-provenance) |
| Point-in-time data | `data/pit.py`, `data/calendar.py`, `data/fundamentals.py` | [architecture.md](docs/architecture.md#point-in-time-rules) |
| Datasets | `data/synthetic.py`, `data/price_sim.py`, `data/edgar.py`, `data/edgar_universe.py`, `data/semi_synthetic.py` | ADR-0003 |
| Research core | `research/features.py`, `research/backtest.py`, `research/leakage.py`, `research/statistics.py`, `research/quality.py` | |
| Workflow | `workflows/engine.py`, `workflows/steps.py`, `workflows/primary.py`, `workflows/faults.py` | ADR-0005 |
| Judgment | `judgment/providers.py`, `judgment/prompts.py` | |
| Gate, approvals, budgets | `services/approvals.py`, `services/budget.py`, `domain/policies.py` | ADR-0004, ADR-0006 |
| MCP server | `server/__init__.py`, `server/data_tools.py`, `server/research_tools.py`, `server/common.py` | |
| HTTP, auth | `http_app.py`, `auth.py` | [deployment.md](docs/deployment.md) |
| Reports, demo, replay | `report.py`, `demo.py` | [runbook.md](docs/runbook.md) |
| Evaluation | `evals.py`, `evals/golden/` | |
| CLI | `cli.py` (`rsf`) | [README](README.md#try-it) |

### Deviations from the original design

- **Analytics use NumPy, not Polars or DuckDB.** The data fits in memory as dense matrices; one library is simpler and deterministic.
- **The in-memory "fakes" for repositories are in-memory SQLite** (RSF-012). The same SQL code then runs in tests and in production, with no second implementation to drift.
- **Evidence IDs are content-derived, not UUIDs.** This makes reruns byte-identical and deduplicates evidence. A `run_evidence` table links evidence to runs, and there are `experiments`, `trial_results`, `step_results`, `approvals`, `api_keys` and `model_usage` tables beyond the original sketch.
- **Standalone analysis tools** (`run_backtest`, `audit_leakage`, …) run the deterministic prefix of the workflow as an auditable `analysis` run, so every result has a run and evidence.
- **A too-short sample yields only `NEEDS_EVIDENCE`.** The other statistics are not treated as evidence either way. The evaluation suite found this.


## Evaluation strategy

Build evaluation before tuning prompts (RSF-032). Minimum dimensions:

1. **Tool correctness:** the right capability is selected with valid arguments.
2. **Evidence fidelity:** material claims resolve to stored evidence.
3. **Calculation fidelity:** numeric outputs match the deterministic reference implementation.
4. **Permission fidelity:** forbidden actions fail closed.
5. **Uncertainty calibration:** insufficient evidence becomes an explicit unknown.
6. **Recovery:** a tool timeout, malformed source data or a partial source outage produces controlled behavior.
7. **Cost and latency:** model and tool costs are traced per run.

Create a golden dataset of at least 25 representative cases before calling the MVP complete. The synthetic fixtures (RSF-008–009) plant a known signal and a known look-ahead leak so the correct answers are known in advance. Add adversarial cases for prompt injection in filing text, stale data, duplicate entities, contradictory evidence and missing required fields.

## Testing

```bash
uv run pytest                      # unit, integration, property, MCP, HTTP, docs and supply-chain tests
uv run rsf eval                    # golden evaluation suite -> var/scorecard.{json,md}
DATABASE_URL=postgresql+psycopg://... uv run pytest tests/test_persistence.py tests/test_postgres.py
```

MCP tools are tested in process with `mcp.Client(create_server(services))` and over HTTP with Starlette's test client. The healthcheck test asserts `structured_content["status"] == "ok"`.

## Observability

Every run should emit:
- `run_id`, `step`, `tool_name`, `model`, latency, and a token and cost estimate;
- input and output schema versions;
- evidence IDs read;
- approval events;
- failure and retry events;
- the final outcome, and whether a human changed the recommendation.

Never log secrets or raw sensitive payloads. Store hashes and IDs where possible.

## Security and threat model

- Use service accounts with least privilege.
- Treat all retrieved text, especially filing text, as untrusted data, never as instructions.
- Keep credentials out of Skills and prompts.
- Enforce scope and roles on the server, not in natural language. Authenticate with hashed, revocable API keys ([ADR-0004](docs/adr/0004-authentication-api-keys.md)).
- Cap model spend per run and per day, so a traffic spike on the public demo can't create an unbounded bill ([ADR-0006](docs/adr/0006-hosting.md)).
- Use read-only data access for discovery and analysis by default.
- For uploaded or fetched documents, keep immutable originals and derived text separately.
- Validate `source_uri` against an allowlist, so the system can't be made to fetch attacker-supplied URLs (SSRF).
- No tool may send email, create tickets, place orders or modify production data without explicit egress rules and an approval record.

## Milestones

Each milestone is broken into tickets in [docs/ROADMAP.md](docs/ROADMAP.md).

| Milestone | Scope | Release |
|---|---|---|
| M0 | Foundations, contracts and fixtures: packaging fix, git, CI, contracts, synthetic fixtures, first golden cases | |
| M1 | Deterministic core: persistence, evidence, audit, point-in-time data, features, backtest, leakage audit, statistics, LLM-free workflow | |
| M2 | MCP surface: narrow typed tools, resources, prompts, server-side policy, integration tests | |
| M3 | Skills, model reasoning and evaluation: eval harness, 25 golden cases, real Skill content, model only at judgment steps | |
| M4 | Approvals and recovery: approval gates, pause and resume, idempotency, retries, failure injection | |
| M5 | Demo and portfolio polish: one-command demo, run report, architecture and threat-model docs, demo recording | **v0.1.0** |
| M6 | Real data: SEC EDGAR, security master, semi-synthetic prices, data quality, snapshots | |
| M7 | Persistence and deployment: Neon Postgres, container, Streamable HTTP + API keys, roles, Fly.io, R2, backups | |
| M8 | Observability and operations: structured logs, model-spend caps, runbook (traces and dashboards optional) | |
| M9 | Hardening and release: security testing, supply chain, reproducibility, release pipeline, pre-recorded runs, public demo | **v1.0.0** |

v1.0 is a portfolio-grade cut ([ADR-0007](docs/adr/0007-v1-scope.md)). Tickets marked `optional` in the roadmap are not required for it.

## Acceptance checklist (v0.1)

Status as of 2026-09-23: **18 of 18 met** (CI is configured; its first run happens when the repository is pushed).

Workflow steps. Each has a deterministic artifact, an audit event and a tested failure path:
- [x] Hypothesis freeze: frozen model, content-hash experiment ID, ledger entry; rejects changes to a frozen hypothesis (`test_contracts.py`).
- [x] Data acquisition: every read stored as evidence with `as_of`; rejects a missing `as_of`; an outage pauses the run (`test_data.py`, `test_workflow.py`).
- [x] Feature build: knowledge-time lineage on every value; malformed input handled (`test_research.py`, golden case 18).
- [x] Backtest: matches hand-computed fixtures; delay and costs applied; point-in-time universe (`test_research.py`).
- [x] Leakage audit: catches the planted leaks and passes the clean fixture (golden cases 02–06, 15).
- [x] Statistical review: deflated Sharpe uses the ledger's trial count; statistics match reference values (`test_research.py`, recomputation in every eval case).
- [x] Economic rationale review: schema-validated; uncited claims rejected (golden case 21).
- [x] Implementation review: capacity, turnover and cost assessment from deterministic inputs.
- [x] Research committee: memo plus a human `ApprovalRecord`; pauses at `needs_review` (`test_workflow.py`).

Cross-cutting:
- [x] Every material recommendation cites evidence or explicitly says evidence is insufficient (automatic evidence-fidelity checks in every eval case).
- [x] All irreversible actions are disabled or human-approved; no trading tool exists (`test_tool_surface_is_exact_and_has_no_trading`).
- [x] Every MCP tool has a typed schema and integration tests (`test_mcp.py`, `test_http.py`).
- [x] At least one Skill is dynamically useful: the point-in-time Skill's script catches the restatement leak in exported lineage (`test_skill_script_accepts_exported_lineage`).
- [x] Every arithmetic, financial or statistical calculation has deterministic tests.
- [x] 28 golden cases are scored on all seven evaluation dimensions.
- [x] A run pauses and resumes across a process restart without re-executing completed steps (`test_resume_after_process_restart`).
- [x] The demo survives one injected tool failure (demo scenario `fault-survived`, golden case 16).
- [x] The package installs from a clean environment (`uv sync --locked`, verified on Python 3.12); CI is configured in `.github/workflows/ci.yml`.

## Remaining owner actions

1. Push to GitHub, confirm CI (including the PostgreSQL job) is green, and protect `main` (RSF-004, RSF-060).
2. Build the container: `docker compose up --build` (RSF-061).
3. Deploy with [docs/deployment.md](docs/deployment.md): Fly.io, Neon, R2 (RSF-067, RSF-079).
4. Run the restore drill in [docs/runbook.md](docs/runbook.md) (RSF-068).
5. Set `ANTHROPIC_API_KEY` and record a Claude baseline: `rsf eval --provider anthropic` (RSF-039).
6. Record the demo with [docs/demo-script.md](docs/demo-script.md) (RSF-052), then tag `v1.0.0` (RSF-078, RSF-080).

## Handoff note to the coding agent
Don't broaden scope until the first vertical slice is demonstrably correct, auditable and restartable. Prefer boring deterministic code over agent autonomy. Every time a model is introduced, document why a deterministic rule is not enough, and define an evaluation for that model-dependent decision.
