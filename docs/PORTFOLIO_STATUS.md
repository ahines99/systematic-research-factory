# Portfolio execution status and owner handoff

Updated 2026-09-27. Audience: **equal AI engineering and quantitative research**. This is the current execution record; the [roadmap](PORTFOLIO_ROADMAP.md) preserves the original gap assessment and task IDs.

## Accepted decisions

Alex accepted the recommended public GitHub/Fly/Neon/R2 approach and supplied `ahines99/systematic-research-factory`. Use GitHub as the portfolio destination for now. Keep Opus 5, free rules-based guests, $1/run and $3/day model caps, a $20 total live-evaluation allowance with a $3 pilot, and a $25/month hosting target with review at a $20 projection. Start Fly at one shared CPU/1 GB in `iad`. Use Neon Free for setup, then confirm a 24-hour recovery window on the chosen launch plan. Use R2 Standard with 90-day retention. No custom domain or paid market-data purchase is required. Actual billing limits and retention still need platform verification.

Alex has Anthropic and Cloudflare accounts; API billing/key readiness and R2 activation are not established. Fly and Neon setup remains an owner dependency. A Claude chat account alone does not establish API access. This execution has made **no paid model calls and provisioned no paid infrastructure**. No release tag or deployment has been created.

## Work completed or prepared

| Roadmap tasks | Delivery and evidence | Remaining boundary |
|---|---|---|
| P01–P02 | Public repository integrated without replacing its initial history; audit fixes and candidate archives committed; publication scan found no matching credential patterns and no API-key rows in archived databases | Automated scanning is bounded, not a guarantee of absence |
| P03 | README/handoff, ADR fallback policy and demo narration reconciled; this status separates current execution from historical audit counts | Owner reviews the public story |
| P04 | Immutable historical source selection, archive checksums, richer current runtime identities and classified cross-CPU comparisons; exact current-runtime tests retained | New v1 release baseline waits for final source/version freeze; historical cross-host comparison is not byte-identical replay |
| P05 | Advisory reachability review and dated [risk register](security-risk-register.md); candidate image scanning added alongside the release gate | Actual final image and residual risk acceptance still required |
| P06 | Hosted CI fully passed on [0107a81](https://github.com/ahines99/systematic-research-factory/actions/runs/36357022307), including PostgreSQL and Python 3.12/3.13/3.14; final presentation/bundle changes go through CI again | See current workflow result for subsequent revisions |
| P07 | [Live evaluation protocol](live-evaluation-protocol.md), paired arms, cases, repeat count, accounting and stop rules prepared | P08–P09 need API access, dashboard comparison and owner sample review |
| P10 | Deployment defaults and exact secret checklist prepared | Real app/database/bucket identifiers and accounts missing |
| P15–P17 | Guided demo page, six application-exported reports, static portfolio, [case study](CASE_STUDY.md) and truthful [recording script](demo-script.md) | Browser connector exposed no browser; visual QA/screenshots and owner narration remain unverified |
| P18 | CI candidate evidence bundle and release attachment automation prepared: wheel, sdist, checksums, scorecard, reports, study and manifest | First actual release publication remains gated |
| P23 | [Contribution/maintenance instructions](../CONTRIBUTING.md), [security reporting](../SECURITY.md) and ownership/teardown expectations prepared; GitHub private vulnerability reporting enabled | Owner takes ongoing billing/security responsibility |
| P25–P26 | Protocol frozen before results; 240 recorded combinations; all records/summaries reproduced exactly in a separate output directory; [research note](research/note.md), data sheet, CSV/JSON and inspected scientific plots | Review simulation interpretation; this is not empirical equity alpha |

Pending acceptance: P08–P14 (live/hosted evidence), browser/client walkthrough, P19–P22 (final freeze, release, deployed acceptance and personal publication). P24, actual prior-published-release replay, is a subsequent-release obligation. Do not describe the portfolio as finalized v1.0 while these remain open.

## What Alex needs to do next

1. **Anthropic API:** enable billing in the API console and set `ANTHROPIC_API_KEY` in the local ignored `.env` or approved platform secret store. Tell the assistant only that it is configured. Do not send the value in chat. Confirm project spending controls; the assistant can then perform the bounded pilot and evaluation, with you checking billed totals and a small sample of outputs.
2. **Cloudflare R2:** activate R2 if necessary. Supply the nonsecret account/bucket identifiers and install a bucket-scoped app credential securely. Keep policy-administration access separate. The assistant can configure/test retention and app access once connected; Cloudflare DNS ownership alone is insufficient.
3. **Fly.io and Neon:** create/sign into the accounts and complete identity/billing/terms yourself. Supply account/team/project identifiers through normal authenticated access. The assistant can provision and configure the agreed small deployment after access is available; do not pre-purchase additional capacity. Confirm the actual Neon restore window and the projected total before paid launch.
4. **Personal review:** read the case study and research note; try the README from a fresh checkout as a first-time reviewer. Focus on explaining the clean/leaky controls, multiplicity, evidence binding and simulation limits. The assistant handles technical fixes. Provide a supported browser/client session for visual and MCP walkthroughs when available.
5. **Video and release:** record the prepared narration and send its public URL when ready; an unlisted video is suitable for review. Then review the concrete final commit, image digest, scan, live/hosted evidence and residual risks. Final approval must refer to those actual deliverables before a `v1.0.0` tag/deploy. No further roadmap-level approval is needed for ordinary preparation.

## Exact credential destinations

| Destination | Names | Purpose |
|---|---|---|
| Local ignored `.env` for the evaluation | `ANTHROPIC_API_KEY`; dedicated `RSF_DATABASE_URL` | Paid pilot, paired study and durable accounting |
| Fly app secrets | `ANTHROPIC_API_KEY`, `RSF_DATABASE_URL`, `RSF_S3_ENDPOINT_URL`, `RSF_S3_ACCESS_KEY_ID`, `RSF_S3_SECRET_ACCESS_KEY` | Application access; use `postgresql+psycopg://…?sslmode=require` for Neon |
| Fly nonsecret configuration | App name, allowed hosts/origins/public URL, `RSF_BLOB_STORE=s3://<bucket>` | Must match the actual resources; current names are templates |
| GitHub `production` environment secrets | `FLY_API_TOKEN`, `RSF_SMOKE_API_KEY` | Scoped deployment token and read-only application viewer key |

Generate the application viewer key only against the actual deployment database; keep it distinct from the model key and from approver access. The assistant must validate secret presence without printing values. Use the [deployment guide](deployment.md) and [runbook](runbook.md) for commands.

## Hosted acceptance still to execute

Verify authenticated/guest behavior, restart persistence, R2 overwrite/delete rejection using the app token, timed isolated database/blob restore, credential rotation, immutable image rollback, and cold-start/memory behavior. Observe costs for seven days alongside final presentation work. Record actual results and failures; configuration files do not prove these controls. Keep the static reports as a fallback if the dynamic demo is stopped.
