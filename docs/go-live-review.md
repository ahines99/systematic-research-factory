# v1.0 go-live review (RSF-080)

Reviewed 2026-09-27 against the [roadmap](ROADMAP.md). Package version remains `0.1.0`; no release is tagged or deployed from this checkout.

**Verdict: unreleased candidate; hosted backend not yet live.** The five-specialist [audit](audits/2026-09-27/README.md) found defects despite previously passing tests. The [remediation record](audits/2026-09-27/remediation.md) preserves its verification results. Subsequent GitHub publication, hosted CI fixes, research and presentation delivery are tracked in [PORTFOLIO_STATUS.md](PORTFOLIO_STATUS.md). That status is authoritative for current owner dependencies.

| Capability | Local acceptance evidence | External acceptance still required |
|---|---|---|
| Authenticated research workflow | Nine stages, role and ownership checks, six recorded demo scenarios, HTTP/MCP tests | Hosted Fly/Neon/R2 operation and client smoke |
| Durable execution | Atomic checkpoints and terminal outcomes, owner-fenced writes, heartbeats, conflict-safe insertions, stale approval rejection | Hosted restart and restore drill |
| Reproducible deterministic artifacts | Archived configuration and snapshots, source/dependency fingerprints, deterministic-only replay, stored candidate archive | Replay an actual previous release using its preserved runtime after the first release exists |
| Grounded reviews | Schema/citation validation, numeric artifact references rendered by code, explicit uncertainty pauses, targeted skill evaluation | Live model baselines and a measured skills treatment/control comparison |
| Bounded paid dispatch | Transactional reservations, output limits, late/refusal accounting, audited reconciliation | Verify supported provider behavior and actual billed usage with the owner's API account |
| Distribution and operations | Hosted CI, build/package/container checks; readiness validates database and archived blobs; release is configured to deploy the scanned digest | First release/deployment run, R2 retention, restore and rollback, measured idle cost |

Passing local tests does not establish investment performance, complete semantic correctness of model prose, or production readiness. Prices are simulated. Listing windows and some EPS values are derived proxies; see [architecture](architecture.md#datasets).

The final local image passes the configured high/critical vulnerability gate after Python/OpenSSL updates. Three Medium and one Low Python scanner matches remain tracked in the remediation report; reassess them before release.

## Required owner or external actions

| Tickets | Action and acceptance |
|---|---|
| RSF-004, RSF-060 | Public remote and successful hosted CI now exist. Keep branch checks enforced for future changes; final candidate status is linked from the execution record. |
| RSF-034, RSF-039 | Supply an API key and preserve distinct live model/skills-on/skills-off scorecards, including exact input, prompt, skill, model and runtime provenance. A deterministic rules run cannot prove a skill improves a model. |
| RSF-065, RSF-067 | Provision Fly, Neon and R2; configure credentials, host allowlists and R2 retention; verify real overwrite/delete behavior under that policy. |
| RSF-068 | Time a restore into isolated infrastructure, read the restored evidence, and replay with the recorded runtime. Record duration and failures. |
| RSF-078, RSF-079 | Exercise delivery of the scanned digest, seed public demo runs, run readiness/MCP/authenticated-client checks, rehearse rollback, and measure idle cost against the roadmap's approximate monthly ceiling. |
| RSF-052 | Record the corrected demo with simulated-data and review-scope limitations visible. |
| RSF-077 | Preserve the first released image and archive; after a subsequent release, prove replay of that prior release in its original runtime. The stored candidate fixture is useful but is not an earlier published release. |
| RSF-080 | Review pre-tag evidence; update both version declarations, regenerate `uv.lock`, update the changelog and run release checks. Tag only after pre-tag approval. Record post-deployment acceptance separately. |

This order avoids requiring the first release to exist before its own tag. External actions are pending acceptance, not claims that the repository has no implementation for them. No cloud account, production credentials or paid calls were used for this remediation.

## Historical evidence

The 2026-09-23 three-agent fixes remain represented by `tests/test_audit_regressions.py`. The 2026-09-27 audit at commit `91e3023` is preserved unchanged as a historical baseline; its test counts and defect descriptions describe that commit. Current results belong in the separate remediation record.

## Drill log

| Date | Environment and immutable version | Drill | Duration | Result |
|---|---|---|---|---|
| Pending | | Restore, archived evidence and replay | | |
| Pending | | Release rollback and client/storage smoke | | |
| Pending | | Idle cost observation | | |
