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

The repository is a **scaffold**. The specification in this document is complete; almost none of it is implemented yet.

| Area | State |
|---|---|
| Version control | Not a git repository yet (RSF-001) |
| Packaging | `pyproject.toml` has dependencies but no `[build-system]`. The `src/` folder is imported as a package (`from src.mcp_server import mcp`), but setuptools treats it as a src-layout root, so a wheel build fails. Tests only pass via `python -m pytest` from the repo root (RSF-002) |
| `src/domain/models.py` | `Confidence`, `EvidenceRef` and `Finding` exist. `AuditEvent` (below) is **not** implemented (RSF-006) |
| `src/domain/project_models.py`, `policies.py`, `services.py` | Not created |
| `src/adapters/`, `src/observability.py` | Not created |
| `src/workflows/` | Empty package; `base.py` and `primary.py` not created |
| `src/mcp_server.py` | `healthcheck` tool and `project://policies` resource only. The `review_run` prompt and all domain tools are missing. Display name updated to "Systematic Research Factory" |
| `skills/*/SKILL.md` | Four files with **identical boilerplate**; only the name differs. They don't yet meet the "dynamically useful Skill" acceptance item (RSF-034–037) |
| `tests/test_mcp.py` | One test, passing. It checks `is_error` but not the returned status |
| `README.md`, `docs/` | README, roadmap and ADRs 0001–0007 written; architecture, data-contract and threat-model docs not written |
| Fixtures, database, Docker | None |

Code blocks in the rest of this document are the **target design** unless marked as existing. Work is tracked as tickets in [docs/ROADMAP.md](docs/ROADMAP.md).


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
| Environment | `uv` with committed `uv.lock` | Not yet installed on the dev machine |
| Build backend | hatchling | Added in RSF-002 |
| MCP | `mcp[cli]` v2 | `MCPServer`, in-process `Client` |
| Contracts | Pydantic v2 | Frozen models for frozen artifacts |
| Operational state | **SQLite for v0.1**, PostgreSQL from M7 | SQLAlchemy 2 + Alembic with portable types only (ADR-0001, RSF-060) |
| Analytics | Polars (and DuckDB where SQL is clearer) | Deterministic feature build and backtest |
| Evidence blobs | Local content-addressed store, then S3-compatible storage with object lock | RSF-013, RSF-065 |
| Workflow | In-house state machine persisted in the operational DB; no workflow engine | [ADR-0005](docs/adr/0005-workflow-state-machine.md) |
| Market data | Real SEC EDGAR filings; semi-synthetic prices keyed to acceptance time; fully synthetic fixtures for tests | [ADR-0003](docs/adr/0003-market-data-semi-synthetic.md) |
| Model access | Anthropic SDK behind a `ModelClient` interface | Deterministic fake for tests (RSF-039) |
| Observability | structlog; OpenTelemetry optional | RSF-069; RSF-070 optional ([ADR-0007](docs/adr/0007-v1-scope.md)) |
| Tests | pytest, in-process MCP client, `hypothesis` for property tests | One async plugin only (RSF-003) |
| Authentication | Bearer API keys with server-side roles; read-only guest with no login; hosted OAuth only if a Claude.ai connector is wanted | [ADR-0004](docs/adr/0004-authentication-api-keys.md) |
| Deployment | Docker, ASGI (Starlette/FastAPI only for non-MCP endpoints) on Fly.io, with Neon Postgres and Cloudflare R2 | [ADR-0006](docs/adr/0006-hosting.md) |

Not used by default: pgvector (no semantic-retrieval need yet), Neo4j (not graph-heavy), dbt (no warehouse).

Keep the agent framework out of the center of the repository. Put orchestration behind interfaces so Claude, another model or a deterministic job can drive the same domain services.


## Project architecture

### MCP capability boundaries
In the MVP these are separate modules in one process (RSF-025). Split them into separate servers only when authorization, lifecycle or deployment needs diverge.

| Module | Responsibility | Example tools |
|---|---|---|
| `sec_pit` | Filings and XBRL facts as known at `as_of`, using SEC acceptance time as knowledge time; restatement-aware | `get_filing_as_of`, `get_facts_as_of` |
| `market_data_pit` | Prices, corporate actions and universe membership as known at `as_of`; survivorship-safe | `get_prices_as_of`, `get_universe_as_of` |
| `factor_research` | Feature build with knowledge-time lineage; leakage audit | `build_features`, `audit_leakage` |
| `backtest` | Deterministic backtests and statistical review | `run_backtest`, `get_statistics` |
| `research_ledger` | Hypothesis freezing, experiment identity, trial counting, runs, evidence, approvals | `freeze_hypothesis`, `start_run`, `get_run_report` |

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

## Data and state model

The workflow database is the source of truth: SQLite in v0.1, PostgreSQL from M7. Migrations use portable types through SQLAlchemy. The DDL below is the PostgreSQL target.

```sql
create table workflow_runs (
  run_id uuid primary key,
  experiment_id text not null,
  project_type text not null,
  status text not null,
  current_step text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  requested_by text not null
);

create table evidence (
  evidence_id uuid primary key,
  run_id uuid references workflow_runs(run_id),
  source_uri text not null,
  source_type text not null,
  as_of timestamptz,
  content_hash text not null,
  metadata jsonb not null default '{}'::jsonb
);

create table findings (
  finding_id uuid primary key,
  run_id uuid references workflow_runs(run_id),
  finding_type text not null,
  statement text not null,
  confidence text not null,
  assumptions jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table finding_evidence (
  finding_id uuid references findings(finding_id),
  evidence_id uuid references evidence(evidence_id),
  relation text not null,
  primary key (finding_id, evidence_id, relation)
);

create table audit_events (
  event_id bigserial primary key,
  run_id uuid references workflow_runs(run_id),
  step text not null,
  actor text not null,
  event_type text not null,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- Added beyond the original spec; needed for experiment identity, idempotency and approvals.
create table experiments (
  experiment_id text primary key,          -- content hash of frozen hypothesis + spec
  research_family text not null,           -- trial counting for the deflated Sharpe ratio
  hypothesis jsonb not null,
  backtest_spec jsonb not null,
  created_at timestamptz not null default now()
);

create table step_results (
  run_id uuid references workflow_runs(run_id),
  step text not null,
  idempotency_key text not null,
  status text not null,
  artifact_evidence_id uuid references evidence(evidence_id),
  created_at timestamptz not null default now(),
  primary key (run_id, step)
);

create table approvals (
  approval_id uuid primary key,
  run_id uuid references workflow_runs(run_id),
  step text not null,
  approver text not null,
  decision text not null,                  -- approved | rejected | needs_more_evidence
  reason text not null,
  created_at timestamptz not null default now()
);
```

`src/domain/models.py` **currently contains** `Confidence`, `EvidenceRef` and `Finding` as below. `AuditEvent` still needs to be added.

```python
# src/domain/models.py
from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field

class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class EvidenceRef(BaseModel):
    source_id: str
    uri: str
    retrieved_at: datetime
    as_of: datetime | None = None
    excerpt_hash: str | None = None

class Finding(BaseModel):
    finding_id: str
    title: str
    statement: str
    confidence: Confidence
    evidence: list[EvidenceRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

# TODO (RSF-006): not yet implemented
class AuditEvent(BaseModel):
    run_id: str
    step: str
    event_type: str
    created_at: datetime
    actor: str
    payload: dict[str, Any] = Field(default_factory=dict)
```


### Project-specific contracts (target, RSF-006)

```python
# src/domain/project_models.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class Hypothesis(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: str = "1"
    hypothesis_id: str
    research_family: str
    statement: str
    created_at: datetime          # must be timezone-aware
    universe: str
    horizon_days: int             # > 0

class BacktestSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: str = "1"
    hypothesis_id: str
    as_of: datetime               # must be timezone-aware
    execution_delay_minutes: int  # >= 0
    transaction_cost_bps: float   # >= 0
    hold_days: int                # > 0
```

The original spec's `frozen: bool = True` field is replaced by true immutability (`frozen=True`) plus a content-hash `experiment_id`.

### Project-specific MCP tools (target, RSF-026)

Tools are thin wrappers; logic lives in services.

```python
# add to the MCP server
@mcp.tool()
def get_filing_as_of(cik: str, as_of: str, form: str | None = None) -> list[dict]:
    return sec_repo.get_as_of(cik=cik, as_of=as_of, form=form)

@mcp.tool()
def run_backtest(spec: BacktestSpec) -> dict:
    return backtester.run(spec.model_dump())

@mcp.tool()
def freeze_hypothesis(h: Hypothesis) -> dict:
    return ledger.freeze(h.model_dump())
```


## Repository layout

Target layout after RSF-002 moves the code into a named package. ✅ = exists today.

```text
02_systematic-research-factory/
├── pyproject.toml                ✅ (needs [build-system])
├── README.md                     ✅
├── IMPLEMENTATION_HANDOFF.md     ✅
├── .env.example
├── docker-compose.yml
├── src/
│   └── research_factory/         (today: src/ with __init__.py)
│       ├── mcp_server.py         ✅ (healthcheck + policies only)
│       ├── mcp/                  sec_pit, market_data_pit, factor_research, backtest, research_ledger
│       ├── domain/
│       │   ├── models.py         ✅ (missing AuditEvent)
│       │   ├── project_models.py
│       │   ├── services.py
│       │   └── policies.py
│       ├── adapters/
│       │   ├── repositories.py
│       │   └── external.py
│       ├── workflows/            ✅ (empty package)
│       │   ├── base.py
│       │   └── primary.py
│       └── observability.py
├── skills/                       ✅ (4 placeholder SKILL.md files)
│   ├── point-in-time-research/SKILL.md
│   ├── financial-research-statistics/SKILL.md
│   ├── signal-red-team/SKILL.md
│   └── research-committee/SKILL.md
├── tests/
│   ├── test_mcp.py               ✅ (1 test)
│   ├── test_workflow.py
│   ├── fixtures/
│   └── golden/
└── docs/
    ├── ROADMAP.md                ✅
    ├── adr/                      ✅ (ADR-0001 to ADR-0007)
    ├── architecture.md
    ├── data_contracts.md
    ├── threat_model.md
    └── runbook.md
```

## Package configuration

`pyproject.toml` exists with the dependencies below. It still needs a `[build-system]` table and package discovery (RSF-002), and dev extras for `hypothesis` and `pytest-cov` (RSF-003). Only one of `anyio` and `pytest-asyncio` should drive async tests; the existing test uses the `anyio` marker.

```toml
[project]
name = "systematic-research-factory"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "mcp[cli]>=2,<3",
  "pydantic>=2.9",
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "httpx>=0.27",
  "structlog>=24.4",
  "opentelemetry-api>=1.27",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "ruff>=0.7", "mypy>=1.12"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```


## MCP server (target)

The existing server has `healthcheck` and `project://policies`. The `review_run` prompt below is not yet implemented (RSF-028), and the policies resource should return structured data rather than a pipe-delimited string (RSF-027).

```python
from __future__ import annotations
from mcp.server import MCPServer
from pydantic import BaseModel

mcp = MCPServer("Systematic Research Factory")

class Health(BaseModel):
    status: str
    version: str

@mcp.tool()
def healthcheck() -> Health:
    """Return service health for diagnostics."""
    return Health(status="ok", version="0.1.0")

@mcp.resource("project://policies")
def policies() -> str:
    """Human-readable operating and safety policies."""
    return "Read-only by default. Material actions require explicit approval."

@mcp.prompt()
def review_run(run_id: str) -> str:
    """Create a user-controlled review prompt for a workflow run."""
    return f"Review workflow run {run_id}. Separate facts, assumptions, and recommendations."

app = mcp.streamable_http_app()
```


## Workflow (target, RSF-022–023)

```python
# workflows/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

class Status(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    COMPLETE = "complete"
    FAILED = "failed"

@dataclass
class RunState:
    run_id: str
    status: Status = Status.PENDING
    current_step: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

class Step(Protocol):
    name: str
    async def execute(self, state: RunState) -> RunState: ...

async def run_steps(state: RunState, steps: list[Step]) -> RunState:
    state.status = Status.RUNNING
    for step in steps:
        state.current_step = step.name
        try:
            state = await step.execute(state)
        except Exception as exc:
            state.errors.append(f"{step.name}: {exc}")
            state.status = Status.FAILED
            return state
        if state.status == Status.NEEDS_REVIEW:
            return state
    state.status = Status.COMPLETE
    return state
```

The production version must also persist each step result before continuing (RSF-022), skip steps that already completed on resume (RSF-043–044), and write an audit event on every transition.

```python
# workflows/primary.py
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol
from .base import RunState, run_steps

@dataclass
class FunctionalStep:
    name: str
    fn: Callable[[RunState], Awaitable[Any]]

    async def execute(self, state: RunState) -> RunState:
        result = await self.fn(state)
        state.artifacts[self.name] = result
        return state

class StepService(Protocol):
    async def execute(self, state: RunState) -> Any: ...

class StepServices(Protocol):
    def for_step(self, name: str) -> StepService: ...

# Each step is wired to a domain service that returns structured data, not prose.
PROJECT_STEPS = [
    "Hypothesis freeze", "Data acquisition", "Feature build", "Backtest",
    "Leakage audit", "Statistical review", "Economic rationale review",
    "Implementation review", "Research committee",
]

async def run_primary(run_id: str, services: StepServices) -> RunState:
    state = RunState(run_id=run_id)
    wired = [FunctionalStep(name=n, fn=services.for_step(n).execute) for n in PROJECT_STEPS]
    return await run_steps(state, wired)
```

## Policy pattern (target, RSF-029)

```python
# domain/policies.py
from pydantic import BaseModel

class ActionDecision(BaseModel):
    allowed: bool
    requires_human_approval: bool
    reason: str

def check_action(action: str, risk_tier: str, has_approval: bool) -> ActionDecision:
    if risk_tier in {"high", "critical"} and not has_approval:
        return ActionDecision(allowed=False, requires_human_approval=True,
                              reason="Material action requires explicit human approval")
    return ActionDecision(allowed=True, requires_human_approval=False, reason="Policy satisfied")
```

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

The existing test (`tests/test_mcp.py`) checks only `is_error`. The MCP v2 `CallToolResult` exposes `structured_content`, so the target test also asserts the payload:

```python
import pytest
from mcp import Client
from src.mcp_server import mcp   # becomes research_factory.mcp_server after RSF-002

@pytest.mark.anyio
async def test_healthcheck():
    async with Client(mcp) as client:
        result = await client.call_tool("healthcheck", {})
        assert result.is_error is False
        assert result.structured_content["status"] == "ok"
```

Until RSF-002 lands, run tests from the repo root with `python -m pytest`.

Add tests for:
- each project-specific MCP tool;
- authorization and approval rejection;
- workflow pause and resume;
- idempotent reruns;
- provenance links;
- deterministic calculation fixtures, including property tests;
- at least one injected dependency failure.

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

Status as of 2026-09-23: **0 of 18 met.**

Workflow steps. Each needs a deterministic artifact, an audit event and a tested failure path:
- [ ] Hypothesis freeze: frozen model, content-hash experiment ID, ledger entry; rejects changes to a frozen hypothesis.
- [ ] Data acquisition: every read stored as evidence with `as_of`; rejects a missing `as_of`; outage gives `NEEDS_EVIDENCE`.
- [ ] Feature build: knowledge-time lineage on every value; malformed input handled.
- [ ] Backtest: matches hand-computed fixtures; delay and costs applied; point-in-time universe.
- [ ] Leakage audit: catches the planted leak and passes the clean fixture.
- [ ] Statistical review: deflated Sharpe ratio uses the ledger's trial count; all statistics match the reference implementation.
- [ ] Economic rationale review: schema-validated; uncited claims rejected.
- [ ] Implementation review: capacity, turnover and cost assessment from deterministic inputs.
- [ ] Research committee: memo plus a human `ApprovalRecord`; pauses at `needs_review`.

Cross-cutting:
- [ ] Every material recommendation cites evidence or explicitly says evidence is insufficient.
- [ ] All irreversible actions are disabled or human-approved; no trading tool exists.
- [ ] Every MCP tool has a typed schema and integration tests.
- [ ] At least one Skill is dynamically useful and not duplicate prompt text.
- [ ] Every arithmetic, financial or statistical calculation has deterministic tests.
- [ ] 25 golden cases are scored on all seven evaluation dimensions.
- [ ] A run pauses and resumes across a process restart without re-executing completed steps.
- [ ] The demo survives one injected tool failure.
- [ ] The package installs from a clean venv, and CI is green.

## First implementation-agent tasks

Follow the v0.1 critical path in [docs/ROADMAP.md](docs/ROADMAP.md#critical-path). Start with:

1. RSF-001 / RSF-002: git init and the package-layout fix.
2. RSF-003 / RSF-004: tooling and CI.
3. RSF-006 / RSF-007: contracts and experiment identity.
4. RSF-008 / RSF-009: synthetic fixtures with a planted signal and a planted leak.
5. RSF-010: the first 10 golden cases, **before** building services.

## Handoff note to the coding agent
Don't broaden scope until the first vertical slice is demonstrably correct, auditable and restartable. Prefer boring deterministic code over agent autonomy. Every time a model is introduced, document why a deterministic rule is not enough, and define an evaluation for that model-dependent decision.
