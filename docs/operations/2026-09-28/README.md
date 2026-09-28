# Hosted acceptance, 2026-09-28 UTC

Candidate source `d0dd403`; [successful hosted pipeline](https://github.com/ahines99/systematic-research-factory/actions/runs/36365241823). The manifest binds evidence files to the deployed immutable image. Tests used actual Fly, Neon and private R2 resources.

| Check | Observed result |
|---|---|
| Image scan | Three Medium and one Low match; no High/Critical matches. |
| PostgreSQL contracts | 67 passed, one SQLite-only parameter skipped on isolated Neon PostgreSQL 18.6; client TLS verified. Scratch branch removed. |
| R2 lock | Write/read passed; overwrite/delete rejected with HTTP 409 `ObjectLockedByBucketPolicy`; original bytes preserved. |
| Official MCP client | All four roles initialized and read; only approver passed the approval-role boundary, then the nonexistent-run lease check rejected mutation. |
| Authenticated research | Researcher froze a separate hypothesis, completed a deterministic backtest and read its report; guest access concealed the private run with NOT_FOUND. No paid model calls. |
| Restore | Point-in-time branch restored all six demos; twelve archived objects read; all six deterministic artifact hashes matched exactly in the same recorded image/runtime. 19.69 seconds including cleanup. |
| Credential rotation | Replacement viewer credential accepted, revoked credential rejected with 401, GitHub deployment secret updated. No key values published. |
| Stop/start persistence | Fly state confirmed stopped, HTTP auto-started it; all six prior reports remained readable. Liveness 6.688s, readiness 7.266s (one observation). |
| Memory | Post-restart application RSS 194,900 KiB, roughly 190 MiB, on one shared CPU/1 GiB. Snapshot only, not a stress-test peak. |
| Browser | Chromium desktop/mobile navigation, simulation disclosure and page overflow checks passed; six screenshots visually inspected. Recovery card title collision is tracked for correction. |

The first restore probe ran before seeding completed and failed its six-demo precondition; its scratch branch was deleted and the failure record is preserved. The second probe ran after seeding and passed. Initial client probes expected generic error codes; inspection confirmed the actual lease-conflict and private-resource concealment contracts, and the probes were corrected. No production approval was attempted on a real run.

The owner accepted Neon Free's six-hour recovery window for this demo. R2's ninety-day object retention is separate from database recovery. One cold start does not establish a latency percentile or availability SLA. Seven-day hosting-cost observation and personal narration require elapsed time and the owner; neither is represented as completed here.

The corrected v1 runtime passed its own full hosted pipeline. Its [immutable image, scan and inspected screenshots](v1-runtime/manifest.json) show six distinct scenario cards, including Data outage survived, after reseeding.

Rollback between the two preserved candidate images passed, then v1 was restored. Every original report remained readable in both versions; total drill duration was 99.34 seconds. [Exact image and timing record](rollback-acceptance.json). This is a candidate rollback drill, not a claim about a previous published release.
