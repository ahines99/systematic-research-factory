# Workflow, persistence and replay audit — 2026-09-27

Read-only component audit. Runtime probes used Python 3.12, SQLite in memory, memory blobs, and an automatically cleaned temporary directory for the file-store probe. No live models, external databases, shared runtime data or application code were changed. Standard test execution belongs to the root auditor.

## What exists

- A real nine-step engine, rather than a scaffold: frozen hypothesis, data snapshot, feature build, backtest, leakage audit, statistics, economic review, implementation review and committee.
- SQLAlchemy repositories and Alembic migrations for SQLite/PostgreSQL; append-only controls for the ledger, evidence, approvals and audit; file, memory and S3 blob adapters with content hashes and integrity checks.
- Retry/backoff and timeout behavior; run leases; paused-run cancellation; completed-step reuse; findings supersession; deterministic gate and separate human approval; usage records and budget checks.
- Persisted structured artifacts, reports in JSON/Markdown/HTML, six curated demos, archived dataset replay and tests for process restart, replay, expected failures, authorization, and baseline concurrency.
- These are substantial implemented capabilities. The remaining issues below affect guarantees that the docs currently describe as complete.

## Verified defects and required engineering work

### W1 — High: checkpoint recovery loses terminal step effects

**Sources:** `src/research_factory/workflows/engine.py:229`, `:262`, `:264`, `:283`, `:371`, `:397`; `src/research_factory/domain/project_models.py:160`.

The engine saves a completed `StepResult`, then appends an audit event, then applies `fail_run` or `run_decision`. Neither terminal effect is in the persisted step result. Recovery skips the completed step without reconstructing those effects. This is a normal crash window, not malformed input.

**Executed repro:** run the actual primary workflow with `make_experiment(timing='period_end')`. Inject `ConnectionError` only when `audit.append` sees `step='Leakage audit', event_type='step_completed'`; the checkpoint has already committed. Restore audit and resume.

Observed:

```text
CHECKPOINT_CRASH needs_review Leakage audit
RESUMED needs_review Research committee GATE reject
```

The mandatory leakage stop was bypassed. The remaining blocking finding still prevents approval through the normal gate, so this finding does not itself demonstrate an approved leaky run. Independently, an actual clean primary workflow was approved by a second actor; injecting the same error at the committee's `step_completed` audit and resuming produced:

```text
COMMITTEE_CRASH needs_review None
COMMITTEE_RESUME complete None ARTIFACT_DECISION approve
```

The run loses its decision while its durable committee artifact still says approve.

**Fix acceptance:** persist the complete outcome and reconcile run status from it, or atomically commit the checkpoint, findings, terminal transition and audit via a transactional outbox. Fault-inject every boundary around step persistence; a blocking leakage run must remain failed after recovery, and a committee decision must survive process loss. Include partial findings and approval/audit commits in the transaction design.

### W2 — High: an expired worker can still execute and commit after takeover

**Sources:** `src/research_factory/workflows/engine.py:244`, `:261`, `:262`; `src/research_factory/persistence/repositories.py:265`, `:298`, `:351`; `src/research_factory/config.py:80`.

Leases renew only before each step. Persistence and status updates do not check lease ownership or a fencing token. Settings allow a lease shorter than a step/retry duration. Even with a long default lease, process suspension can reproduce the same ordering.

**Executed repro:** in-memory services with `lease_seconds=.05`, timeout 1 second; one custom step sleeps .15 seconds for its first execution and .2 seconds for its second. Advance worker 1 at time 0 and worker 2 at .08 seconds.

```text
worker1 RETURN complete
worker2 ERROR ConflictError
EXECUTIONS [1, 2] WINNING_ARTIFACT {'worker': 1}
```

The expired original owner wins after worker 2 has legitimately taken the lease; both executed. Existing tests only prove rejection while a lease remains live.

**Fix acceptance:** heartbeat long execution, reject stale-owner writes using a monotonically increasing fencing token in transactional predicates, and cancel work on lease loss. Validate configuration as a secondary defense. Add takeover-during-step and takeover-before-commit tests; the old owner must never persist or complete the run after takeover.

### W3 — High: timed-out model calls can finish uncharged while retries issue more calls

**Sources:** `src/research_factory/workflows/steps.py:36`, `:542`, `:543`, `:544`; `src/research_factory/workflows/engine.py:304`, `:332`; `src/research_factory/services/budget.py:35`.

Model calls run in abandonable threads. Usage is written only after the awaiting coroutine receives the response. A timed-out thread continues, its result is discarded, and the retry starts another call. Returned usage from abandoned calls is never recorded; therefore the spend cap cannot see it. This is more serious than the ordinary overshoot of allowing one call just below a soft cap.

**Executed repro:** subclass `EconomicRationaleStep` only to provide an empty payload; inject a fake synchronous provider whose `judge` sleeps .1 seconds then returns usage of 10 input tokens, 10 output tokens and $1. Set timeout .02 seconds and two attempts. After waiting for both fake calls to finish:

```text
RUN needs_review REASON TIMEOUT: Economic rationale review exceeded 0.02s
CALLS 2 FINISHED 2 ACCOUNTED (0, 0.0)
```

No paid API was contacted. The execution/accounting defect is verified; dollar loss with a real provider was not exercised.

**Fix acceptance:** record a durable request/usage reservation before dispatch, reconcile completed responses even after caller timeout, conservatively retain unknown spend, and prevent uncontrolled overlapping retries. Apply the same accounting lifecycle to refusal/no-text responses and usage-write outages. Verify two slow fake calls cannot leave zero usage/reservations and exceed the configured cap unnoticed.

### W4 — Medium: file blobs use a shared per-process temporary pathname

**Sources:** `src/research_factory/persistence/blobs.py:62`, `:64`.

Two threads writing identical new bytes share `<hash>.tmp<PID>`. Both may write the same temporary file; once one renames it, the other's rename has no source. On Windows, read-only target races can also matter, although that variation was not reproduced.

**Executed repro:** two `ThreadPoolExecutor` calls to `FileBlobStore.put(b'same bytes')` in a temporary directory. A barrier after the real `Path.write_bytes` makes both reach rename; a lock around the real `os.replace` forces sequential rename scheduling. One returns the hash and the other raises `FileNotFoundError [WinError 2]`. The hooks only select a valid concurrent ordering.

**Fix acceptance:** unique temporary files per write, race-safe publication, integrity verification of an already-published destination, and cleanup on failure. A barrier-based test with many identical concurrent puts must return the same digest for every writer with a readable, correct blob and no temporary leftovers.

### W5 — Medium: replay executes judgment calls and does not archive its execution configuration

**Sources:** `src/research_factory/demo.py:33`, `:223`, `:236`; `src/research_factory/workflows/steps.py:410`, `:518`; `src/research_factory/workflows/engine.py:80`; `docs/ROADMAP.md:683`.

`DETERMINISTIC_STEPS = 8` includes the economic and implementation judgment steps. `replay_run` executes those with today's service provider and budget. With a live provider it can incur cost and naturally produce different judgments. The replay also uses today's thresholds and implementation; runs do not archive a full settings/code/environment manifest. The idempotency key contains experiment, step name and prior artifact IDs, not implementation/configuration version. Dataset snapshots alone do not establish old-release reproducibility.

**Executed repro:** a counting wrapper around `RulesProvider` runs a normal workflow then calls `replay_run`:

```text
REPLAY_MODEL_CALLS 2 IDENTICAL True STEPS 8
```

Byte identity here depends on the deterministic fake/rules provider. The live API was intentionally not contacted. Source inspection establishes that the same replay path dispatches today's configured provider; the original prompt/skill/configuration is not reconstructed. Existing replay tests use rules and regenerate contemporary runs, rather than executing a preserved release archive under its recorded runtime.

**Fix acceptance:** define exact replay as the six deterministic steps; separately load archived judgment outputs without dispatching a model, or explicitly label a new review as a paid re-evaluation. Persist code revision, dependency/platform identity, thresholds and other result-affecting settings with the run. Add an archived prior-release fixture and a provider that raises if replay calls it. Changing current thresholds must not silently change historical replay semantics.

### W6 — Medium: replay snapshot pins leak into concurrent ordinary runs

**Sources:** `src/research_factory/demo.py:234`, `:241`; `src/research_factory/workflows/steps.py:142`, `:145`; `src/research_factory/services/container.py:49`.

Replay temporarily mutates `services.pinned_snapshots[dataset]` for every run sharing that service container. Acquisition trusts that dictionary instead of selecting inputs per run, and stamps the snapshot with the new experiment's `as_of`. Two overlapping replays can also replace/pop each other's pin. The current CLI normally owns its own process, reducing immediate exposure, but the shared library/service behavior is incorrect under concurrency.

**Executed repro:** create an original two-step run with as-of 2022-01-01; replay it. Interleave an ordinary two-step run requesting as-of 2023-12-30 after the pin is installed and before replay finishes. A wrapper around `WorkflowEngine.start` only arranges that schedule; acquisition/persistence are unmodified.

```text
CONTAMINATED_ASOF 2023-12-30T00:00:00+00:00 LAST_SESSION 2021-12-31
```

The ordinary run consumes the earlier archived snapshot and presents it under the later cutoff.

**Fix acceptance:** make pinned evidence an immutable per-run execution input, or use a fully isolated replay service context with a private pin mapping. Concurrent replay and ordinary acquisition, and two overlapping replays with different snapshots, must each retain their intended evidence without shared mutable overrides.

## Additional gaps from inspection, not independently reproduced

- Evidence insertion and trial-result insertion use select-then-insert; concurrent identical writes can raise `IntegrityError`. Step-result replacement also lacks a status predicate in the final update. Normal ownership reduces same-run contention but does not eliminate cross-run evidence races. Add database-level conflict-safe inserts, collision verification and real concurrent same-experiment tests.
- Finding identity omits evidence, metadata, confidence and severity; reinserting an identical finding ID only reactivates the old record and does not refresh evidence links. A recovered attempt can therefore retain old provenance when its statement stays the same. Define attempt-specific finding identity/provenance and test it.
- `advance` fetches the ledger record after claiming but before its `try/finally` (`engine.py:185`), so an exception there skips lease release. Cancellation (`BaseException`) does not pause the run, although the lease normally releases; the operational handling should be explicit.
- A failed audit append during error recovery can prevent the pause transition itself. Durable audit plus state change needs transaction/outbox semantics; catching more exceptions cannot guarantee progress when the database is unavailable.
- Retry timeouts do not bound synchronous work that never yields, such as some statistics, leakage scans and persistence calls. Default datasets are small; large-input responsiveness was not load-tested.
- HTML reports omit the structured report's statistics and approval details that Markdown includes. This is presentation completeness work, not a security defect.
- Append-only audit retrieval has a 10,000-event default without report pagination/truncation indication. Long-lived retry-heavy runs can silently omit later events.

## Recommended order

1. Repair checkpoint atomicity/reconciliation and lease fencing together.
2. Repair model-call accounting and retry cancellation semantics before paid operation.
3. Make replay scope/configuration explicit and isolate its inputs.
4. Harden concurrent blob/repository writes, then extend failure-injection and concurrency regression coverage.

The security auditor separately owns the stale approval versus newly recomputed committee gate finding; it is not duplicated here.
