# v1.0 go-live review (RSF-080)

Reviewed 2026-09-23 against the production criteria in [ROADMAP.md](ROADMAP.md#what-production-means-here).

**Verdict: not yet live.** All code, tests and configuration for v1.0 are complete and verified locally. The remaining work (10 roadmap tickets) needs the owner's accounts, a GitHub remote, an API key or a recording; it is listed below. `v1.0.0` should be tagged only after they are done.

| Criterion | Evidence | Status |
|---|---|---|
| A hosted, authenticated MCP server runs the full workflow on real SEC EDGAR filings with semi-synthetic prices | `rsf serve` app with API-key auth and roles (`http_app.py`, `auth.py`), tested over HTTP (`tests/test_http.py`). EDGAR universe snapshot of 44 companies (`data/snapshots/`). Golden cases 14–15. `fly.toml`, `Dockerfile` | Code verified; **hosting pending owner** |
| Runs are durable, resumable, idempotent and reproducible | Persisted step results, resume after restart (`test_resume_after_process_restart`), idempotent reuse, byte-identical replay from archived snapshots (`test_replay_from_archived_snapshot_is_byte_identical`, `test_replay_ignores_live_data_changes`) | Done |
| Numbers come from deterministic, tested code; model judgments are schema-validated, cited and evaluated | Hand-computed and property tests (`tests/test_research.py`), independent recomputation in every eval case, judgment contract (`judgment/contract.py`), 28 golden cases passing (`rsf eval`) | Done for the rules provider. **A Claude baseline is pending an API key** (`rsf eval --provider anthropic`) |
| Approvals are enforced server-side by role; no path to order placement | `ApprovalService`, permission table, tests in `test_workflow.py` and `test_http.py`. The tool surface is asserted to contain no trading tools (`test_tool_surface_is_exact_and_has_no_trading`) | Done |
| Structured logs, model-spend caps, backups, a runbook and a release pipeline exist and have been exercised | Redacted JSON logs (`observability.py`), budgets (`services/budget.py`, tests), [runbook.md](runbook.md), `.github/workflows/release.yml` | Logs and caps done. **Backup drill and first release run pending owner** |
| A public demo lets anyone browse pre-recorded runs without logging in, at a bounded cost | `/demo` pages, six recorded scenarios (`rsf demo`), guest rate limit and daily live-run cap (`test_demo_pages_and_guest_live_runs`) | Code verified; **hosting pending owner** |

## Verification performed

- 152 automated tests pass on Python 3.14 (dev) and on Python 3.12 using the locked dependencies (`uv.lock`). Two more (PostgreSQL workflow and concurrency) run in the CI `postgres` job.
- `ruff`, `ruff format --check` and `mypy --strict` are clean over 65 source files.
- `rsf serve` was run as a real process: health, demo pages, guest and keyed MCP calls, a 401 for a bad key, a guest live run and JSON step logs were all checked with curl.
- The golden evaluation suite passes 28 of 28 cases, including 7 adversarial ones; all 7 dimensions are green.
- `pip-audit` found no known vulnerabilities in the locked dependency set.
- The wheel contains the Skills, the EDGAR snapshot and the migrations.

## Not verified here, and why

| Item | Why it wasn't run | What to do |
|---|---|---|
| CI on GitHub (RSF-004), incl. the PostgreSQL job (RSF-060) and the concurrency test | No remote repository; no PostgreSQL or Docker on the build machine | Push to GitHub, confirm the `ci` workflow is green, and protect `main` |
| Container build (RSF-061) | No Docker on the build machine | `docker compose up --build`, or let the release workflow build it |
| Fly.io + Neon + R2 deployment (RSF-067, RSF-079) | Needs the owner's accounts and secrets | Follow [deployment.md](deployment.md) |
| Restore drill (RSF-068) | Needs a Neon project | Follow [runbook.md](runbook.md#restoring-from-backup-rsf-068) and record the time here |
| First tagged release (RSF-078) and demo recording (RSF-052) | Needs a GitHub remote and a person at the keyboard | Tag `v1.0.0` after the items above; record using [demo-script.md](demo-script.md) |

## Open risks

See [threat_model.md](threat_model.md#residual-risks). In short: bearer keys are not scoped to IP addresses, the guest rate limit is per machine, the injection scanner is heuristic (the real control is structural), and artifact hashes can differ between CPU architectures in the last floating-point bit.

## Drill log

| Date | Drill | Duration | Result |
|---|---|---|---|
| | Restore from Neon point-in-time branch + `rsf replay` | | |
