# Deployment

Target: Fly.io (app), Neon (PostgreSQL), Cloudflare R2 (evidence blobs), per [ADR-0006](adr/0006-hosting.md). Provisioning and hosted verification need the owner's accounts. Local builds, distribution checks and smoke tests run before those actions.

## One-time setup

1. **Neon:** create a project and copy the pooled connection string. Enable point-in-time restore and note the plan's retention window, which RSF-068 needs.
2. **Cloudflare R2:** create bucket `rsf-evidence`, then an API token with **Object Read & Write only on that bucket**.
   - R2 tokens cannot leave out delete, so **add a bucket lock rule** (retain all objects for the agreed 90 days). The lock is what enforces object retention: the app's conditional puts stop overwrites, and the lock stops deletes even with a leaked token.
3. **Fly.io:**

   ```bash
   fly launch --no-deploy --copy-config      # uses fly.toml; change `app` and the hosts first
   fly secrets set \
     RSF_DATABASE_URL='postgresql+psycopg://…?sslmode=require' \
     RSF_S3_ENDPOINT_URL='https://<account-id>.r2.cloudflarestorage.com' \
     RSF_S3_ACCESS_KEY_ID='…' RSF_S3_SECRET_ACCESS_KEY='…' \
     ANTHROPIC_API_KEY='…'
   # Deploy through the tagged release workflow after the setup below.
   ```

   `release_command = "rsf init-db"` runs the migrations before each release.

   `fly.toml` sets `RSF_TRUST_PROXY_HEADERS = "true"`, so the guest rate limit keys on Fly's `fly-client-ip` header. Turn it off anywhere the app is not behind Fly's proxy, because a client could set that header itself.
4. **Prepare the release smoke key before the first deploy:** in a trusted local shell with the production `RSF_DATABASE_URL`, run `uv run rsf init-db`, then `uv run rsf keys create --owner release-smoke --role viewer`. Store the one-time key as the `RSF_SMOKE_API_KEY` GitHub production-environment secret; never put it in a file or workflow output. This avoids a first-release dependency on an already-running server.
5. **Demo:** the release workflow starts the machine through a health request and seeds the six scenarios with `rsf --provider rules demo`. Seeding and the release smoke use no paid model calls. For a manual repair, start the specific machine and run `fly ssh console -C "rsf --provider rules demo"`.
6. **Create user keys:** run `fly ssh console -C "rsf keys create --owner <name> --role researcher"` (or `approver`, `viewer`). The key is shown once.
7. **GitHub:** create a protected `production` environment with `FLY_API_TOKEN` and `RSF_SMOKE_API_KEY`. The GHCR image may stay private: the deployment job authenticates with its read-only package token, pulls the scanned digest, authenticates to Fly's registry, and copies that exact digest before deployment. No production rebuild occurs. See [Fly registry authentication](https://fly.io/docs/flyctl/auth-docker/) and [private-registry deployment](https://fly.io/docs/blueprints/using-the-fly-docker-registry/).

## Releasing

Update the version in `pyproject.toml` and `src/research_factory/__init__.py`, run `uv lock`, and turn the changelog candidate into a dated release entry. Run `uv lock --check`, `uv run python scripts/check_release.py vX.Y.Z`, the complete CI checks, and the local deployment checks below. Commit the version fields, lock and changelog together. Then tag `vX.Y.Z` and push the tag. `.github/workflows/release.yml` then:

1. checks the tag, both version declarations and the lock; runs the entire reusable CI workflow, including lint, types, tests, PostgreSQL, rules evaluations, dependency audit, distributions and container smoke;
2. builds the image and scans it (failing on high-severity issues that have a fix) **before** pushing it to GHCR;
3. generates a CycloneDX SBOM and attaches it and the immutable image digest to the GitHub release;
4. pulls the exact GHCR digest, copies it to the authenticated Fly registry, checks digest equality, and deploys that digest with a rolling strategy;
5. seeds the free demo, checks the expected version, `/readyz`, public reports, MCP initialization/tool discovery and guest reads, invalid-key rejection and a viewer-key read. Production deployments are serialized.

The candidate production configuration uses Python 3.14.7 from a verified `python:3.14-slim-bookworm` digest. Both build and runtime layers upgrade OpenSSL/libssl3 to Debian security revision `3.0.22-1~deb12u1`; the base image still contained an older revision when verified. Python 3.14 avoids the Python 3.13-and-earlier tarfile issue described in the [official Python security announcement](https://mail.python.org/archives/list/security-announce@python.org/thread/EFJWGAZJA56AKSBR2WHMHQZO7RRLZPRH/). Image scanning remains a candidate/release gate. CI covers Python 3.12, 3.13 and 3.14; preserved candidate archives have separately classified Linux numerical comparisons. See the [CPU replay finding](audits/2026-09-27/ci-followup.md). No hosted deployment has yet been verified.

Build inputs use a digest-pinned Python image and uv image, a locked application dependency set and GitHub Actions pinned to verified release commit SHAs (the release tags remain in comments). The build-backend dependency is not an immutable source pin. Update them deliberately and rerun the full validation.

The first release is `v1.0.0`; there is no separate v0.1 release ([ADR-0009](adr/0009-production-defaults.md)). Complete code and local checks before tagging; record hosted smoke, rollback and restore results after deployment before declaring go-live complete. Do not claim that the first release has been exercised before it runs.

## Local deployment checks

```bash
uv build --out-dir var/distributions
uv run python scripts/check_distributions.py var/distributions
docker compose up --build --wait --wait-timeout 180
uv run python scripts/smoke_deployment.py http://127.0.0.1:8000 --record-runs var/container-runs.json
docker compose restart app
uv run python scripts/smoke_deployment.py http://127.0.0.1:8000 --expect-runs var/container-runs.json
```

The distribution check installs the wheel and locked dependencies into an isolated environment, runs demo/eval from another directory, and runs the shipped source-distribution tests. Compose runs PostgreSQL and the unprivileged application with persistent volumes; keep the volumes for persistence verification. CI removes only its own isolated stack afterwards. `/healthz` is liveness; `/readyz` checks the database and archived seeded evidence, and remains unavailable until a demo exists.

## Rollback

```bash
fly releases                    # find the last good release's image
fly deploy --image <image-ref>  # redeploy it
```

Migrations are additive. If a release added a migration that must be undone, run `alembic downgrade` against a restored copy first. Never downgrade production in place. Rehearse one rollback to a previous known image, check the deployed version and client smoke, then redeploy the intended image; record the images, timestamps and result in the go-live drill log.

After provisioning, record the selected Neon restore retention window and measured idle monthly cost for Fly, Neon and R2 against the approximately $25/month target. These are owner acceptance evidence, not values inferred from configuration.

## Cost controls

- The machine auto-stops when idle (`min_machines_running = 0`).
- `RSF_BUDGETS__MAX_COST_USD_PER_DAY` caps model spend globally ($3.00 in `fly.toml`). When the cap is hit, keyed runs pause and guest live runs are refused until the next UTC day. `rsf usage` shows today's spend.
- Guests browse pre-recorded runs. Live guest runs use the deterministic rules reviewer, so they never spend model budget, and they are limited to `RSF_BUDGETS__MAX_GUEST_LIVE_RUNS_PER_DAY`.

## Connecting a client

```bash
claude mcp add --transport http rsf https://<app>.fly.dev/mcp --header "Authorization: Bearer rsf_…"
```

Without the header, the client connects as a guest: read-only access to data and demo runs.
