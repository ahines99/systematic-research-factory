# v1.0 release review

Reviewed 2026-09-28 UTC. The hosted service is live. The 1.0.0 package declarations and recovery-card fix are merged at `f4d438f`; tagging and post-release acceptance are separate actions. See [current release publication](https://github.com/ahines99/systematic-research-factory/releases).

## Concrete evidence

- [All ten checks passed for the implementation](https://github.com/ahines99/systematic-research-factory/actions/runs/36364743327) and [the v1 runtime preparation](https://github.com/ahines99/systematic-research-factory/actions/runs/36366266733).
- [Hosted acceptance](operations/2026-09-28/README.md): actual Neon contracts/TLS, R2 lock rejection, official MCP client and authenticated research, isolated restore with exact replay, viewer rotation, stop/start persistence and inspected desktop/mobile screenshots.
- Original deployed candidate: `registry.fly.io/systematic-research-factory@sha256:e53a73e28057107a5e896ab938066980ed761de61d9f8b2686197ad7c0e31981`. Full scan and checksums are in the operational evidence directory.
- [Quant study](research/note.md): 240 prespecified simulation combinations, twenty held-out worlds and complete raw results; no empirical-alpha claim.
- [Live experiment](live-evaluation-protocol.md): development failures retained, one uncertain response held conservatively, frozen paired comparison reported separately. Offline governance success is not live-model reliability.

## Accepted limits and residual risks

Alex accepted the six-hour Neon Free recovery window and ninety-day R2 retention. The app uses one shared CPU/1 GiB in iad, private storage, free rules-based guest runs, $1/run and $3/day hosted model caps. The separately authorized local experiment keeps a $20 lifetime cap inclusive of prior calls and uncertain holds.

The scan has three Medium and one Low Python matches, no High/Critical matches. The [risk register](security-risk-register.md) retains the advisory analysis and review date. Model grounding can reject paid responses; latency and output correctness are measured limitations, not claims erased by increasing budgets. Actual billing for the original lost response remains unknown; its entire reservation stays held at the owner's instruction to continue.

Personal narration, blinded usefulness ratings and seven-day cost observation are human/time-dependent work. They are not fabricated or described as complete. They also do not prevent the free rules demo, published research or operational evidence from being reviewed now. A future prior-published-release replay must use that preserved release's actual runtime; the completed candidate restore is not relabeled as such.

## Drill log

| UTC date | Environment | Drill | Duration | Result |
|---|---|---|---|---|
| 2026-09-28 | Isolated Neon child, original Fly candidate, private R2 | Restore after demo seeding, read twelve objects, exact replay of six deterministic steps | 19.69s including cleanup | Passed; child removed |
| 2026-09-28 | Same production candidate | Viewer credential rotation and revoked-key denial | Recorded requests | Passed; GitHub secret updated |
| 2026-09-28 | Single Fly machine | Confirm stopped, HTTP auto-start, reread six original reports | Ready after 7.266s | Passed; one observation |
| 2026-09-28 | Desktop and mobile Chromium | Page/navigation/disclosure/overflow checks and visual inspection | Pipeline artifact | Passed; recovery title collision corrected in next candidate |
| 2026-09-28 onward | Fly/Neon/R2 billing | Seven-day actual cost observation | Requires elapsed time | [Open log](operations/cost-observation.md) |

The initial restore probe intentionally retained its failed completeness check when it raced seeding. No production database reset, migration downgrade, or real-run approval was used in these drills. Release/rollback image evidence and post-tag results are appended when executed.

## Historical record

The [five-specialist audit](audits/2026-09-27/README.md), [remediation](audits/2026-09-27/remediation.md) and [cross-CPU replay investigation](audits/2026-09-27/ci-followup.md) remain preserved. Their original source revisions and test counts are historical evidence.

## Finalization authorization and v1 candidate

The owner explicitly instructed completion of all remaining assistant work and finalization of the project. This authorizes publication after the technical checks; it does not imply that the owner supplied human sample ratings or personally reviewed every artifact. The assistant performs and records the technical pre-tag review.

The v1 runtime candidate passed [the full hosted pipeline](https://github.com/ahines99/systematic-research-factory/actions/runs/36366507618), including the corrected six-scenario browser check. Source: `f4d438f7b28bf0702e6a01e0b314188a62ccb34c`. Image: `registry.fly.io/systematic-research-factory@sha256:22248d65630702a8ddd0c66e0f9c69d1967ef91264e90712800b27d84bbfc9fe`. [Scan, screenshots and manifest](operations/2026-09-28/v1-runtime/manifest.json) preserve the actual candidate. The final tag adds the published experiment/operational record and release-evidence attachment checks; it does not change the frozen model prompts or quantitative implementation.

The [candidate rollback drill](operations/2026-09-28/rollback-acceptance.json) passed in both directions in 99.34 seconds. The intended v1 candidate is restored and all original reports remain readable.
