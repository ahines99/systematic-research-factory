# Deployment

Target: Fly.io (app), Neon (PostgreSQL), Cloudflare R2 (evidence blobs), per [ADR-0006](adr/0006-hosting.md). Everything here needs the owner's accounts, so these steps are run by the owner.

## One-time setup

1. **Neon:** create a project and copy the pooled connection string. Enable point-in-time restore and note the plan's retention window, which RSF-068 needs.
2. **Cloudflare R2:** create bucket `rsf-evidence`, then an API token with **Object Read & Write only on that bucket**.
   - R2 tokens cannot leave out delete, so **add a bucket lock rule** (for example, retain all objects for 3 years). The lock is what makes evidence tamper-proof: the app's conditional puts stop overwrites, and the lock stops deletes even with a leaked token.
3. **Fly.io:**

   ```bash
   fly launch --no-deploy --copy-config      # uses fly.toml; change `app` and the hosts first
   fly secrets set \
     RSF_DATABASE_URL='postgresql+psycopg://…?sslmode=require' \
     RSF_S3_ENDPOINT_URL='https://<account-id>.r2.cloudflarestorage.com' \
     RSF_S3_ACCESS_KEY_ID='…' RSF_S3_SECRET_ACCESS_KEY='…' \
     ANTHROPIC_API_KEY='…'
   fly deploy --remote-only
   ```

   `release_command = "rsf init-db"` runs the migrations before each release.

   `fly.toml` sets `RSF_TRUST_PROXY_HEADERS = "true"`, so the guest rate limit keys on Fly's `fly-client-ip` header. Turn it off anywhere the app is not behind Fly's proxy, because a client could set that header itself.
4. **Seed the demo:** the machine auto-stops, so start it first (`fly machine start`), then run `fly ssh console -C "rsf --provider rules demo"`. This records the six scenarios that guests browse at `/demo`. Use the rules reviewer, so seeding costs nothing and the outcomes match `evals/demo_manifest.json`.
5. **Create keys:** run `fly ssh console -C "rsf keys create --owner <name> --role researcher"` (or `approver`, `viewer`). The key is shown once.
6. **GitHub:** add a `FLY_API_TOKEN` repository secret and a `production` environment for the release workflow. The GHCR image can stay private: Fly builds its own image from the tagged commit (`--remote-only`), and GHCR holds the scanned copy with its SBOM.

## Releasing

Tag `vX.Y.Z` and push the tag. `.github/workflows/release.yml` then:

1. runs the tests and the golden evaluation suite;
2. builds the image and scans it (failing on high-severity issues that have a fix) **before** pushing it to GHCR;
3. generates a CycloneDX SBOM and attaches it to the GitHub release;
4. deploys with a rolling strategy and smoke-tests `/healthz` on the app named in `fly.toml`.

The first release is `v1.0.0`; there is no separate v0.1 release ([ADR-0009](adr/0009-production-defaults.md)).

## Rollback

```bash
fly releases                    # find the last good release's image
fly deploy --image <image-ref>  # redeploy it
```

Migrations are additive. If a release added a migration that must be undone, run `alembic downgrade` against a restored copy first. Never downgrade production in place.

## Cost controls

- The machine auto-stops when idle (`min_machines_running = 0`).
- `RSF_BUDGETS__MAX_COST_USD_PER_DAY` caps model spend globally ($3.00 in `fly.toml`). When the cap is hit, keyed runs pause and guest live runs are refused until the next UTC day. `rsf usage` shows today's spend.
- Guests browse pre-recorded runs. Live guest runs use the deterministic rules reviewer, so they never spend model budget, and they are limited to `RSF_BUDGETS__MAX_GUEST_LIVE_RUNS_PER_DAY`.

## Connecting a client

```bash
claude mcp add --transport http rsf https://<app>.fly.dev/mcp --header "Authorization: Bearer rsf_…"
```

Without the header, the client connects as a guest: read-only access to data and demo runs.
