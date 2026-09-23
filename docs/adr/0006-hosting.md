# ADR-0006: Fly.io + Neon + Cloudflare R2, with hard model-spend caps

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-060, RSF-065, RSF-067, RSF-068, RSF-071, RSF-079, RSF-082

## Context
The deployment is a low-traffic portfolio service. It should cost close to nothing at idle and survive a traffic spike, such as a Hacker News post, without a surprise bill. Hosting costs are small and predictable. **Model spend is the real financial risk**, because every live run calls a model at up to three judgment steps.

## Decision
| Concern | Choice |
|---|---|
| App | One container on **Fly.io**; machines stop automatically when idle |
| Database | **Neon** serverless PostgreSQL, which scales to zero |
| Evidence blobs | **Cloudflare R2**, S3-compatible with no egress fees |
| Environments | Production plus local. A separate staging environment is optional |
| Config | `fly.toml` and environment documentation committed in the repo; secrets set through the platform's secret store |

Cost controls:
- **Hosting target:** about $25 a month or less at idle, excluding model spend.
- **Model spend:** a global daily cap and a per-run token budget (RSF-071). Runs that exceed a budget pause with an audit event.
- **Public demo:** defaults to **pre-recorded runs** (RSF-082), which are exact replays made possible by data snapshots (RSF-059). Live guest runs are limited to a small number per day.

Durability:
- Neon's point-in-time restore covers the database. Check the retention window of the chosen plan.
- Evidence is content-addressed and written once. The app's storage credentials cannot delete or overwrite objects. Check R2's bucket lock or retention features in RSF-065.
- A restore is rehearsed once (RSF-068).

Provider choices can change within the same shape (for example Render instead of Fly.io, Supabase instead of Neon, S3 instead of R2) without a new ADR.

## Alternatives considered
- **Cloud Run + Cloud SQL:** Cloud SQL doesn't scale to zero and would dominate the cost.
- **A single VPS:** cheapest, but patching, TLS and backups become our job.
- **Kubernetes:** out of proportion for one container.

## Consequences
- Cold starts add latency to the first request after an idle period. That's acceptable for a demo.
- Three providers means three sets of credentials, all managed as platform secrets.
- The demo stays affordable no matter how much traffic it gets.

## Revisit when
There's sustained real usage, the monthly bill exceeds budget, or a provider's free or low tiers change.
