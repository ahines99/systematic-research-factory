# Hosting cost observation

Observation opened 2026-09-28 UTC. Owner: Alex Hines. Target: below $25/month combined Fly, Neon and R2; investigate at a $20 monthly projection. This record contains no inferred bills.

The deployment starts with one shared CPU/1 GiB Fly machine in iad, automatic stop/start, shared IPv4, no attached volume, Neon Free and R2 Standard. Restore-test branches were removed. Initial model evaluation is a separate $20 lifetime allowance and must not be mixed into hosting cost estimates.

| UTC date | Fly accrued/projected | Neon usage/charge | R2 storage/requests/charge | Combined projection | Action |
|---|---|---|---|---|---|
| 2026-09-28 | Not yet observed | Free plan verified; actual usage pending | Private bucket/lock verified; actual usage pending | Unmeasured | Observation opened |
| 2026-09-29 | Pending | Pending | Pending | Pending | |
| 2026-09-30 | Pending | Pending | Pending | Pending | |
| 2026-10-01 | Pending | Pending | Pending | Pending | |
| 2026-10-02 | Pending | Pending | Pending | Pending | |
| 2026-10-03 | Pending | Pending | Pending | Pending | |
| 2026-10-04 | Pending | Pending | Pending | Pending | |
| 2026-10-05 | Pending | Pending | Pending | Pending | Seven-day review |

Read each provider's billing/usage console, record the covered period and actual values, and link a redacted export if useful. Do not record payment details or credentials. A few hours of charges are not a seven-day measured baseline; report uncertainty in projections. If the projection reaches $20, inspect machine uptime, database compute and storage/request growth before adding capacity. Keep the static portfolio available if the dynamic demo needs to be stopped.

Maintenance dates: reassess the tracked Python advisories by 2026-10-04; renew the app-scoped GitHub Fly deployment token before its ninety-day expiry in late December 2026. Alex's researcher and approver credentials remain separate from the rotated read-only deployment smoke credential.
