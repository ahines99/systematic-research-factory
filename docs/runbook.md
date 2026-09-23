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

Only one worker advances a run at a time, holding a lease that it renews before each step (`RSF_LEASE_SECONDS`, 15 minutes by default). If the worker dies, the run stays `running` until the lease expires. After that, `rsf resume <run_id>` takes it over. Before expiry, resume returns `CONFLICT`.

## Replaying a run

`rsf replay <run_id>` re-executes the deterministic steps from the snapshot archived with the run and compares artifact hashes. Exit code 0 means byte-identical; 4 means something changed, and the JSON output shows which step. Use it when a result is questioned, and before and after dependency upgrades.

## Rotating keys

```bash
rsf keys list
rsf keys create --owner <name> --role <role>   # give the new key to its owner
rsf keys revoke <old-key-id>                   # takes effect on the next request
```

For platform secrets (Anthropic, R2, database): create the new credential, `fly secrets set` it (this restarts the machine), confirm `/healthz` and one tool call, then revoke the old credential at the provider.

## Restoring from backup (RSF-068)

1. In Neon, create a branch from the point in time before the incident. Note its connection string.
2. Point a scratch copy at it: `RSF_DATABASE_URL=<branch-url> rsf runs --limit 5`, then `rsf replay <a recent run_id>`. The replay proves that the database and the R2 evidence agree.
3. If the copy is good, switch production: `fly secrets set RSF_DATABASE_URL=<branch-url>`.
4. Record the start and end times of the drill in [go-live-review.md](go-live-review.md).

Evidence blobs in R2 are write-once and content-addressed, so a database restore never loses a blob. A replay detects any blob that is missing or altered.

## A source is down

EDGAR outages affect only `rsf edgar` (rebuilding the snapshot), because runs read the committed snapshot. If a future live source is down, runs pause with `UPSTREAM_UNAVAILABLE` after retries; resume them later.

## The model provider is down or refusing

Judgment steps pause (`UPSTREAM_UNAVAILABLE`, or `NEEDS_EVIDENCE` for a refusal); deterministic steps are unaffected. To keep working without the model, set `RSF_MODEL_PROVIDER=rules` and resume. The judgment artifacts record which provider produced them.

## The daily model-spend cap was reached

Keyed runs pause at their next judgment step, and guest live runs return 429, until 00:00 UTC. Guest runs cost nothing (they use the rules reviewer), but the cap stops all live work to be conservative. Run `rsf usage` to see today's spend and the costliest runs. Raise `RSF_BUDGETS__MAX_COST_USD_PER_DAY` only deliberately, and note it in the changelog.

## Health and logs

- `GET /healthz` returns `{"status": "ok", "version": …}`.
- Logs are JSON on stderr with `run_id`, `step` and `tool_name`, with secrets redacted: `fly logs`.
- The audit trail for a run is in `rsf show <run_id>`, or the `run://{run_id}` resource.
