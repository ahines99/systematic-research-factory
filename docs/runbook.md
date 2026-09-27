# Operations runbook

Commands assume a shell with the app's environment: `fly ssh console` in production, or a local checkout.

## A run is stuck in `needs_review`

`rsf show <run_id>` prints the report; the reason prefix says why the run paused.

| Reason prefix | Meaning | Action |
|---|---|---|
| `APPROVAL_REQUIRED` | Waiting for the committee | An approver runs `rsf approve <run_id> --decision … --reason … --approver <name>` (or the `approve_run` tool) |
| `UPSTREAM_UNAVAILABLE` / `TIMEOUT` | A data source was down after retries | When it's back: `rsf resume <run_id>`. Completed steps are reused |
| `NEEDS_EVIDENCE` | Bad data or rejected reviewer output | Read the findings. Fix the data or re-run with a new experiment. Resuming repeats the failing step |
| `BUDGET_EXCEEDED` | A per-run or daily model budget was hit | Wait for the next UTC day, or raise the budget deliberately, then `rsf resume <run_id>`. `rsf usage` shows the spend |
| `INTERNAL` | An unexpected error (a bug) paused the run instead of leaving it `running` | Check `fly logs` for `engine_error` or `step_error`. Fix the cause, then `rsf resume <run_id>` |

A paused run that should not continue can be ended: `rsf cancel <run_id> --reason "…" --actor <name>`. It becomes `failed` with reason `CANCELLED by <name>: …`. Only its requester or an approver can cancel it (the `cancel_run` tool enforces this).

## A run is stuck in `running`

Only the current lease owner may publish workflow state. The lease is heartbeated during long work and renewed before each step (`RSF_LEASE_SECONDS`, 15 minutes by default). If the worker dies, the run stays `running` until the lease expires. After that, `rsf resume <run_id>` takes it over. Before expiry, resume returns `CONFLICT`. A stale worker cannot publish after takeover. Preserve the run's recorded runtime for resume; changing code or dependencies is not a transparent continuation.

## Replaying a run

`rsf replay <run_id>` re-executes only the six deterministic steps from archived snapshots and threshold settings; it makes no model calls or new human decisions. Exit code 0 means byte-identical; 4 means artifact differences. A missing or mismatched runtime manifest returns a typed `CONFLICT` (CLI exit 2). Use the preserved source/dependency/platform runtime, normally the original immutable release image. Test an upgrade using new runs; do not relabel an old archive as produced by the upgraded runtime.

## Rotating keys

```bash
rsf keys list
rsf keys create --owner <name> --role <role>   # give the new key to its owner
rsf keys revoke <old-key-id>                   # takes effect on the next request
```

For platform secrets (Anthropic, R2, database): create the new credential, `fly secrets set` it (this restarts the machine), confirm `/healthz` and one tool call, then revoke the old credential at the provider.

## Restoring from backup (RSF-068)

1. In Neon, create a branch from the point in time before the incident. Note its connection string.
2. Point a scratch copy of the run's recorded release image at it: `RSF_DATABASE_URL=<branch-url> rsf runs --limit 5`, then `rsf replay <a recent run_id>`. Confirm matching runtime identity, archived evidence availability and exact artifact comparisons.
3. If the copy is good, switch production: `fly secrets set RSF_DATABASE_URL=<branch-url>`.
4. Record the start and end times of the drill in [go-live-review.md](go-live-review.md).

Evidence blobs in R2 are content-addressed and protected by the configured retention policy. Confirm the retained objects cover the restored database; replay and readiness checks detect missing or altered evidence. Retention policy expiry and operator/account changes must be considered in the drill.

## A source is down

EDGAR outages affect only `rsf edgar` (rebuilding the snapshot), because runs read the committed snapshot. If a future live source is down, runs pause with `UPSTREAM_UNAVAILABLE` after retries; resume them later.

## The model provider is down or refusing

Judgment steps pause (`UPSTREAM_UNAVAILABLE`, or `NEEDS_EVIDENCE` for a refusal); deterministic steps are unaffected. To keep working without the model, set `RSF_MODEL_PROVIDER=rules` and resume. The judgment artifacts record which provider produced them.

## The daily model-spend cap was reached

Keyed runs pause at their next judgment step, and guest live runs return 429 when settled usage has reached the daily cap. Guest reviews cost nothing. UTC midnight resets the settled daily window, but pending/uncertain reservations remain charged until settled or reconciled, and per-run caps do not reset. Inspect both `rsf usage` and `rsf usage --pending`. Raise `RSF_BUDGETS__MAX_COST_USD_PER_DAY` only deliberately, and note it in the changelog.

## Health and logs

- `GET /readyz` checks a database read and retrieves seeded public-demo evidence; it returns unavailable before demo seeding or when those dependencies fail. Run `python scripts/smoke_deployment.py https://<app>.fly.dev --version <version> --require-key` with a viewer key in `RSF_SMOKE_API_KEY` to verify readiness, MCP and authentication without paid calls.
- `GET /healthz` returns `{"status": "ok", "version": …}`.
- Logs are JSON on stderr with `run_id`, `step` and `tool_name`, with secrets redacted: `fly logs`.
- The audit trail for a run is in `rsf show <run_id>`, or the `run://{run_id}` resource.

## An uncertain model call or reserved budget blocks retry

A timeout or worker crash can leave the provider call outcome unknown. The durable reservation remains charged against the cap and blocks another call for that step. Do not refund it or retry while the original worker/provider might still complete.

1. Run `rsf usage --pending` and identify the reservation and its run/step.
2. Check provider request logs or billing and confirm the original worker and provider call have finished. Record actual model, input/output tokens and cost, including a confirmed zero only when evidence supports it.
3. Reconcile from the trusted operator CLI:

   ```bash
   rsf reconcile-usage <reservation-id> --actor <operator> \
     --reason "provider request and billing verified; original worker finished" \
     --confirmed-finished --model <model-id> \
     --input-tokens <count> --output-tokens <count> --cost-usd <actual-cost>
   ```

4. Review the appended usage/audit record and only then resume the run. The HTTP surface cannot reconcile spend. Keep the reservation when the outcome is still unknown.

## Release rollback and cost evidence

Follow [deployment.md](deployment.md#rollback), record both image digests, verify version/readiness/MCP after rollback, and restore the intended release. Record the drill timestamps and outcome in the go-live review. Also record the chosen database restore retention and measured idle hosting cost after provisioning; configuration alone does not establish either acceptance criterion.
