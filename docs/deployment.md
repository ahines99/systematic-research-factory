# Deployment

Target: Fly.io (app), Neon (PostgreSQL), Cloudflare R2 (evidence blobs), per [ADR-0006](adr/0006-hosting.md). Everything here needs the owner's accounts, so these steps are run by the owner.

## One-time setup

1. **Neon:** create a project and copy the pooled connection string. Enable point-in-time restore and note the plan's retention window, which RSF-068 needs.
2. **Cloudflare R2:** create bucket `rsf-evidence`, then an API token with **Object Read & Write only on that bucket**, without delete. Optionally add a bucket lock rule for retention.
3. **Fly.io:**

   ```bash
   fly launch --no-deploy --copy-config      # uses fly.toml; change `app` and the hosts first
   fly secrets set \
     RSF_DATABASE_URL='postgresql+psycopg://…?sslmode=require' \
     RSF_S3_ENDPOINT_URL='https://<account-id>.r2.cloudflarestorage.com' \
     RSF_S3_ACCESS_KEY_ID='…' RSF_S3_SECRET_ACCESS_KEY='…' \
     ANTHROPIC_API_KEY='…'
   fly deploy
   ```

   `release_command = "rsf init-db"` runs the migrations before each release.
4. **Seed the demo:** `fly ssh console -C "rsf demo"` records the six scenarios that guests browse at `/demo`.
5. **Create keys:** run `fly ssh console -C "rsf keys create --owner <name> --role researcher"` (or `approver`, `viewer`). The key is shown once.
6. **GitHub:** add a `FLY_API_TOKEN` repository secret and a `production` environment for the release workflow.

## Releasing

Tag `vX.Y.Z` and push the tag. `.github/workflows/release.yml` then:

1. runs the tests and the golden evaluation suite;
2. builds the image, publishes it to GHCR, generates a CycloneDX SBOM and scans the image (failing on high severity);
3. attaches the SBOM to the GitHub release;
4. deploys with a rolling strategy and smoke-tests `/healthz`.

## Rollback

```bash
fly releases                    # find the last good release's image
fly deploy --image <image-ref>  # redeploy it
```

Migrations are additive. If a release added a migration that must be undone, run `alembic downgrade` against a restored copy first. Never downgrade production in place.

## Cost controls

- The machine auto-stops when idle (`min_machines_running = 0`).
- `RSF_BUDGETS__MAX_COST_USD_PER_DAY` caps model spend globally. When the cap is hit, runs pause and guest live runs are refused until the next UTC day.
- Guests browse pre-recorded runs; live guest runs are limited to `RSF_BUDGETS__MAX_GUEST_LIVE_RUNS_PER_DAY`.

## Connecting a client

```bash
claude mcp add --transport http rsf https://<app>.fly.dev/mcp --header "Authorization: Bearer rsf_…"
```

Without the header, the client connects as a guest: read-only access to data and demo runs.
