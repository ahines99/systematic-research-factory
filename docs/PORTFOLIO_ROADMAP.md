# Roadmap to a finished portfolio project

Prepared 2026-09-27 from the current worktree, the five-agent audit and remediation evidence, release workflows, demo surfaces, and existing scope decisions. This is the actionable finishing plan. [ROADMAP.md](ROADMAP.md) remains the engineering ticket specification; the [remediation report](audits/2026-09-27/remediation.md) remains the record of completed repairs.

**Assessment:** the research engine is substantially implemented and locally verified. The remaining work is release integration, live-provider and hosted acceptance, presentation, publication, and a small maintenance handoff. It is not ready to call a finalized public portfolio project yet. This review did not repeat the full code audit or rerun the application suites; verification counts below refer to the recorded remediation runs.

Confirmed audience: **equal emphasis on AI engineering and quantitative research**, per Alex's direction. The finished project must demonstrate both governed AI systems and credible research methodology. Preserve the accepted public-repository, Fly/Neon/R2, free guest demo, and first-release `v1.0.0` decisions unless Alex changes them. No new paid calls, infrastructure, publication, or release is authorized by this planning document.

## What finished means

A visitor should understand the problem in under a minute, inspect a successful run and a deliberately rejected run without credentials, and find evidence for the engineering claims. A technical reviewer should be able to clone the released revision, run the offline demo, inspect the evaluation results, and trace a report to its artifacts. Alex should be able to explain the design, its limits, and how to operate or shut down the hosted demo.

Completion requires:

1. A public, reviewed repository and a tagged release with green hosted CI and downloadable evidence.
2. A working public demo, a short video, authentic screenshots, and a concise case study linked from the README and portfolio page.
3. A live-model compatibility baseline and an honestly reported skills-on/off comparison, with failures and cost included. A positive skill effect is not required; an unsupported claim of improvement is unacceptable. A separate reproducible quantitative research note must demonstrate what the signal, controls and robustness checks establish under the simulated-data assumptions.
4. Verified hosted authentication, storage retention, recovery, restart and release rollback, with the deployed image tied to the scanned digest.
5. Consistent documentation, disclosed simulated-data and review limitations, a risk register, and a lightweight maintenance/shutdown plan.

An actual **previous published release** replay is a subsequent-release obligation. Preserve the first release now; do not invent an earlier release or make a circular prerequisite for the first tag. A local/video-only portfolio could be published sooner, but that would be an explicit smaller scope than the currently accepted hosted v1.0.

## Evidence already available

| Area | Existing evidence | What it does not establish |
|---|---|---|
| Research and governance | Nine workflow stages, four skills, six demo scenarios, point-in-time lineage, approvals, durable checkpoints and budget reservations | Investment performance, full model-prose entailment, or every external red-team analysis |
| Tests | Final Windows and Linux suites: 287 passed and 4 documented skips each; separate PostgreSQL run: 67 passed and 1 skip | Hosted CI or all behavior on external services |
| Offline evaluations | 37/37 cases and 339/339 dimension checks; nine adversarial cases | Live model quality or benefit from skills |
| Distribution | Installed wheel demos/evals and extracted source-distribution tests passed | Publicly downloadable release assets or a fresh clone from GitHub |
| Container | Non-root runtime, readiness, authentication, persisted reports after restart and exact replay passed locally | Fly/Neon/R2 operation, resource sizing, retention, restore or billing |
| Supply chain | Dependency audit passed; image passed its high/critical fixed-vulnerability gate | Zero vulnerabilities: three Medium and one Low Python scanner matches remain |

The exact local evidence is in [remediation-verification.json](audits/2026-09-27/remediation-verification.json). Treat it as dated evidence, not a permanent certification.

## Remaining gap register

**Required** means needed for the accepted portfolio finish. **Conditional** means needed only for a claim or surface we keep. **Follow-up** means it can remain openly scheduled after the first release. These are planning priorities, not security severity ratings.

| ID | Gap and observed basis | Priority | Closure tasks |
|---|---|---|---|
| G01 | The remediation is uncommitted; this checkout has no Git remote or release tags. No hosted CI evidence exists. | Required | P02, P06, P20 |
| G02 | Release migration of replay fixtures is unresolved. Matching-platform tests assert the entire archived runtime equals current runtime; changing package version, source, skills or recorded dependencies breaks that equality by design. The archive script preserves databases, blobs and runtime metadata, not a self-contained copy of the old executable environment. A simple `1.0.0` bump is therefore insufficient. | Required | P04, P19 |
| G03 | Historical and current statements conflict. `IMPLEMENTATION_HANDOFF.md` still reports 187 tests, 30 evals and a pending container build. ADR-0009 retains the superseded fallback wording below its amendment. The demo script says to clear `var/`, claims about two seconds, and describes model/human activity while running a deterministic scripted demo. | Required | P03, P15 |
| G04 | There is no live Anthropic baseline, API compatibility/billing proof, or measured skills treatment/control report. The model pricing comment is dated before some listed models; provenance should be refreshed. | Required for the current LLM-assisted project claim | P07–P09 |
| G05 | Four image advisories remain. Their reachability, treatment and review date have not been recorded as a release decision. | Required disposition; patch when appropriate | P05 |
| G06 | Fly app/host values are templates; real accounts, scoped credentials, database retention and bucket-lock behavior are unverified. | Required | P10–P12 |
| G07 | Registry copying, migrations, demo seeding and smoke checks have not run through the real release path. Rollback has not been rehearsed on hosted infrastructure. | Required | P13, P20–P21 |
| G08 | No timed hosted restore, credential rotation drill, cold-start/resource measurement or observed cost record exists. The 512 MB Fly configuration is not a measured sizing conclusion. | Required, bounded demo scope | P13, P14, P21 |
| G09 | README has no live-demo/video links or screenshots. No portfolio case study or recruiter-facing project card exists in the repo. | Required | P16, P17, P22 |
| G10 | Public demo browsing exists, but it is a basic run list with a raw POST example. Visual/accessibility/browser QA and a guided visitor path are unrecorded. | Required visitor polish; live-run button conditional | P15 |
| G11 | Wheels/source archives and full scratch logs remain under ignored `var/`. Release automation attaches an SBOM and image digest, but does not currently publish the complete wheel/sdist/checksum/eval/demo evidence bundle. | Required release evidence; package registry optional | P18, P20 |
| G12 | Clean-clone onboarding, one real MCP client interaction and a first-time reviewer walkthrough remain unverified. | Required | P06, P09, P17 |
| G13 | Public contact/support expectations, update cadence, incident response ownership, credential teardown and a stable offline fallback are not assembled into a maintainer handoff. | Required, lightweight | P23 |
| G14 | Prior-release replay cannot yet be demonstrated because no published release exists. Broader load, licensed prices, OAuth, full external red-team analyses and semantic model guarantees remain outside demonstrated scope. | Follow-up or conditional scope expansion | P24; exclusions below |
| G15 | Unit tests and six demo outcomes do not form a standalone quantitative research study. There is no portfolio research note with a frozen design, out-of-sample simulation controls, sensitivity results and uncertainty interpretation. | Required for the confirmed equal emphasis | P25, P26 |
| G16 | The SEC-derived snapshot has documented caveats, but no concise public data/methodology sheet brings together universe selection, availability timing, derived EPS, listing proxies, simulated-price construction and their consequences for inference. | Required for the confirmed equal emphasis | P25, P26 |

Presentation gaps are missing evidence or assets, not claims of a newly demonstrated security exploit. The UI has not undergone visual inspection in this planning pass.

## Execution plan: my actions and your actions

All tasks below are **planned**, not completed by writing this roadmap. I can prepare code, documentation, configurations, tests and evidence. You own account identity, billing, access grants, personal presentation and final publication decisions. Once those are supplied and execution is authorized, I can perform routine technical steps; they do not all need to become manual tasks for you.

### Phase 1 — Make the candidate safe to evolve and publish

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P01 — Confirm finish criteria | Write a project pitch with equal AI-engineering and quantitative-research emphasis and keep a claim-to-evidence checklist. Preserve current scope and spending defaults. | Audience confirmed; supply any deadline or narrower target roles, and change hosted/public scope only if you want a smaller cut. | Finish checklist and exceptions recorded. No dependency. |
| P02 — Publication hygiene and durable source | Review the complete diff and Git history for credentials, private paths, personal information and inappropriate generated data; inspect archived databases before publication. Separate source/evidence from disposable scratch output. Prepare coherent commits with audit lineage preserved. | Supply the GitHub account/organization and repository name; confirm public visibility and publication authorization. | Reviewed changes are committed with a stable revision; no secrets or runtime credentials are included. P01. |
| P03 — Documentation reconciliation | Refresh the handoff; mark old counts as historical; remove active contradictions in ADR prose; fix anchors; reconcile README, roadmap, runbook and go-live status. Clarify rules/model reviews and scripted/human approvals. | Review the concise project story for accuracy; no technical edits required. | A reader finds one current status and no stale completion claims. P01. |
| P04 — Replay across releases | Preserve the candidate archives unchanged and capture their actual source/runtime. Add explicit current-release and historical-runtime replay paths. Run historical artifacts in their preserved implementation; current code must reject incompatible artifacts explicitly. Add a separately reviewed baseline only after final source/version freeze. | None unless deciding to expand retention or hosting spend. | A version/source change can pass release CI without deleting old evidence, regenerating test expectations, or treating a mismatch as successful replay. P02; final new baseline waits for P19. |
| P05 — Residual security treatment | Refresh dependency/image scans, inspect the four remaining matches and application exposure, apply suitable stable fixes, and document any unresolved advisory with rationale, owner, mitigation and review date. Revisit build-backend and mutable external tool pins where practical. | Accept any justified residual risk before release, or choose to delay it. | Release image passes policy; unresolved risks are explicit. A prerequisite runtime change feeds P04. |
| P06 — Hosted CI and clean clone | Configure the remote after authorization, push the reviewed branch, run all existing CI jobs including Python 3.13, PostgreSQL, distributions and container smoke. Fix failures. Exercise README commands in a fresh clone with no hidden `var/` assets; configure required checks and branch protections through available access. | Create/sign into GitHub if needed and grant the necessary repository access; enable account-only protection settings if automation cannot. | Hosted checks pass on the exact candidate commit, fresh-clone demo works, and protections are verified. P02–P05. |

**Phase gate:** a public-reviewable candidate with reproducible source and working hosted CI. Presentation drafting and account setup can start before this gate; final baselines cannot.

### Phase 2 — Establish real model evidence

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P07 — Account, model and evaluation protocol | Check the configured model and current pricing/structured-output support, estimate calls and cost, select cases and repeat count before results, and prepare a separate persistent accounting database and distinct arm outputs. Retain the accepted Opus 5 default unless a change is agreed. | Enable Anthropic API billing, install the key through a local/platform secret store, and authorize a total evaluation allowance. Do not paste keys into chat. | A written, bounded experiment plan exists, with per-run/day/total allowance and stop conditions. P01. |
| P08 — Compatibility and usage pilot | Make a minimal live structured-output call and a small representative workflow set; record requested/returned model, schema/refusal behavior, tokens, latency, reservations and settlement. Compare recorded usage with available provider usage/billing evidence. Investigate discrepancy before scaling up. | Grant read access to relevant usage records or confirm dashboard totals. | Live contract and accounting work; no unexplained pending reservations. P07 and explicit spend authorization. |
| P09 — Paired evaluation and client proof | Run the predefined live skills-on/off protocol with the same cases/configuration and separate artifacts; include PIT, evidence fabrication, uncertainty and scoped review cases. Report which cases actually used a model, failures, costs and repeat variability. Manually inspect a small blinded sample; demonstrate one real MCP client workflow with roles and approval boundaries. | Review a small set of anonymized outputs for usefulness and wording; provide/sign into the preferred client if needed. | A publishable evaluation report and live-client record exist. No claim of uplift unless results support it; inconclusive or negative results are reported honestly. P06, P08. |

The current 37-case suite includes deterministic/scripted paths; requesting the Anthropic provider does not make all 37 cases live-model tests. Publish the actual live count. Do not tune against the reported evaluation set and present the tuned result as an independent test. A budget-limited pilot is useful but must be labelled as such.

### Phase 2B — Demonstrate quantitative research, not only quant-themed infrastructure

This work can proceed while API/cloud access is being arranged. It uses the existing synthetic and SEC-timed datasets; it does not require a licensed price subscription. It may require a small deterministic study harness and additional analysis artifacts, so finish it before the final source freeze.

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P25 — Research protocol and data/methodology sheet | Freeze the earnings-drift question, feature definition, trading/availability assumptions, universe, trial ledger, primary metrics and evaluation split before examining new study results. Describe all 44-company snapshot selection limits, SEC timing, derived EPS, listing proxies and simulated-price construction. Choose independent development/evaluation seeds or worlds, a no-signal control, a planted-signal control and the deliberate leakage control. Specify cost/delay, concentration and parameter sensitivity checks with clear scope. | Confirm the research story you want to defend in an interview; review the assumptions and study protocol. | A concise preregistered simulation study and data sheet exist. Evaluation conditions are held out from tuning, and existing demo scenarios are not relabelled as unseen data. P01, P03. |
| P26 — Run the study and publish a research note | Implement a reproducible command-driven study; compute results deterministically and publish labeled charts/tables. Compare clean versus leaky estimates, null versus planted-signal behavior, frozen temporal/seed evaluation results, costs/delays, concentration, and reasonable parameter changes. Report sample/trial counts, uncertainty and failures; check independent seeds rather than relying on one attractive path. Explain multiplicity, serial dependence, and the limits of the chosen Sharpe/DSR/bootstrap assumptions. Include references to primary methodological sources and link every figure to machine-readable results. | Review the interpretation and practice explaining why this is a methodology demonstration rather than evidence of tradable alpha. | A research note, protocol, data sheet, deterministic runner and result artifacts reproduce from the released environment. Results may be weak or negative; validity and honesty are the acceptance criteria. P25; integrate focused regressions before P19. |

The displayed quantitative evidence should include a signal/portfolio definition, an equity or cumulative-return chart explicitly labelled simulated, a clean/leaky/control comparison, risk/turnover/drawdown summaries where computed, sensitivity results, and an uncertainty table. For measures not currently implemented, add the smallest independently validated calculation needed for the stated study. Do not fill missing measures with model estimates. A small simulation does not justify precise false-positive or power claims; choose repeat counts and report uncertainty before making those claims.

Keep this study distinct from the live-model experiment: model-quality variation and return uncertainty are different quantities. The note can demonstrate that governance catches known errors without claiming that every statistical test is calibrated for every strategy.

### Phase 3 — Provision and verify the hosted system

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P10 — Accounts and deployment configuration | Prepare the precise Fly app/region, Neon database, R2 bucket, host/origin settings, access matrix and secret names; replace template values. Prepare a cost worksheet separating hosting, model calls and optional domain expense. | Sign into/create Fly, Neon and Cloudflare accounts; add billing where required; select an approved monthly ceiling and database/blob retention. A custom domain is optional. | Resource identifiers, limits and access are supplied securely. P01; provisioning needs your spending authorization. |
| P11 — Database and evidence storage | Provision through available authorized access, apply migrations, configure least-privilege application credentials, enable chosen restore history and R2 retention. Use a dedicated test object to verify attempted overwrite/delete denial without touching evidence. Document administrative ability to alter policies. | Complete account-only verification prompts; approve the retention policy before it creates a storage commitment. | Selected restore window is recorded and locked-object tests pass using the app credential. P10. |
| P12 — Release secrets and first deployment setup | Configure the GitHub production environment, scoped deployment token and viewer smoke key, private registry access if needed, migrations and demo seeding. Keep production secrets out of Git, logs and screenshots. Deploy a reviewed candidate only after infrastructure and publication authorization. | Grant deployment access and approve the concrete target/resources; complete any unavailable environment approval controls. | The real candidate is reachable and its runtime settings match the reviewed configuration. P06, P11. |
| P13 — Hosted acceptance and restore | Run guest/readiness/MCP/keyed checks, verify cross-role and private-run restrictions, persisted reports after restart and archive reads. Measure cold/warm startup, normal demo memory and completion time. Restore into an isolated database using the recorded image; verify retained blobs and exact replay; time the drill. | Confirm the measured user experience and recovery objective are acceptable. | A dated hosted evidence record includes resource sizing and successful isolated restore. No production database is overwritten for the drill. P12. |
| P14 — Cost and lifecycle observation | Observe representative idle/demo use for at least seven days; record dates, uptime settings, storage and billed/estimated amounts, and project monthly hosting cost separately from model spend. Check whether monitoring traffic prevents scale-to-zero. Set a low-noise health check and billing alerts where supported. | Confirm billing alerts reach you and approve any change to budget or availability. | A dated measured-period cost record and labelled monthly projection fit the accepted ceiling; actual month-end spend follows later. P12; runs in parallel with portfolio work. |

Keep guest browsing and guest scenarios free of paid model calls. A static report/video fallback should remain accessible when the app is asleep or unavailable. Normal demo sizing and usability checks are required here; an enterprise throughput benchmark is not.

### Phase 4 — Turn the implementation into a convincing portfolio

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P15 — Visitor path and demo truthfulness | Curate a concise entry page linking clean, leakage and overfit cases; explain gate status, evidence and simulated prices in plain language. Add useful report navigation. Replace the raw API instruction with a clearly optional developer section or an accessible live-run control if retained. Check desktop/mobile layout, keyboard use, contrast, errors and empty states. Rewrite the recording script using isolated demo storage instead of clearing `var/`. | Choose a simple visual direction and give feedback on a first reviewable page. | A first-time visitor can inspect success/failure and trace a cited artifact without a terminal or login. The recording describes actual rules/model and approval behavior. P03; final captures after P13. |
| P16 — Showcase assets and case study | Capture authentic UI screenshots; create a readable architecture diagram and a short case study giving equal space to the AI design and the quantitative study. Cover hard failures fixed, live-model results, signal/controls, research sensitivity, cost and limitations. Prepare a project card and evidence-backed resume bullets for both audiences. Add README demo/video/research-note links and real CI badges once URLs exist. | Choose personal positioning, approve claims and supply the destination portfolio page. | README and portfolio entry tell a coherent story with working links and no fabricated impact metrics. P09, P13, P15, P26 for final evidence; drafting can start sooner. |
| P17 — Recording and independent walkthrough | Prepare a reproducible 3–4 minute shot list and captions; rehearse the commands, capture visuals where tools allow, and package a stable downloadable example report. Use a fresh viewer session and clean clone for a final walkthrough. Fix confusing steps. | Record the personal narration/presentation if desired, approve the final video, and choose its host. Spend roughly 30 minutes following the README or arrange one first-time reviewer. | Public video and offline fallback work, and a new reviewer can complete the try-it path. P15–P16. |
| P18 — Public evidence bundle | Add release artifacts for wheel, sdist, checksums, SBOM, immutable image reference, version/commit manifest, sanitized scorecards, quantitative study outputs and representative reports. Publish useful summarized evidence, not arbitrary workstation logs or credentials. Keep audit history available but separate it from the visitor path. | Confirm intended public information and any personal contact details. | A stranger can download the release and inspect its supporting evidence; essential artifacts are not only in ignored local storage. P06, P09, P16, P26. PyPI publication is optional. |

### Phase 5 — Freeze, release and sign off

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P19 — Freeze the release | Complete source/skill changes, update both version declarations to `1.0.0`, regenerate the lock, date the changelog, and create the reviewed release baseline(s) using P04. Re-run checks appropriate to all changes, including complete release CI and artifact installation. Preserve exact source/dependencies/image. | Review release notes and the residual-risk summary. | One identifiable release candidate passes all checks; no fixture is silently rewritten to conceal incompatibility. P04–P09, P15, P18. |
| P20 — Publish and deploy | Present the concrete candidate commit, asset list and deployment target. After publication authorization, tag/push and execute the scanned-digest release path; capture CI/release URLs, registry digest equality and deployed version. | Approve the prepared public release and any required protected-environment gate. | `v1.0.0` and its artifacts are public; the deployed digest is the scanned digest; post-deploy smoke passes. P11–P13, P19. A tag triggers deployment, so it is not a harmless bookkeeping step. |
| P21 — Rollback and go-live | Rehearse rollback between preserved compatible candidate/release images, run client/storage checks, then restore the intended release. Ensure paused historical runs are resumed only in a compatible runtime; document schema compatibility. Update go-live evidence and all public links. | Accept measured recovery, availability, cost projection and unresolved risks; approve the portfolio claims. | Release, rollback, restore, live model and public-demo evidence are linked to actual versions. P13–P14, P20. A candidate rollback drill is not labelled previous-published-release replay. |
| P22 — Portfolio publication | Supply the final project card, case study, screenshots, video links and technical talking points. Update the portfolio site through available access once authorized. | Publish/pin the project on your chosen portfolio/GitHub profile and use the approved resume material; authorize any external posting separately. | The project is discoverable from your professional profile, all links work in an anonymous session, and the finish checklist is signed off. P16–P17, P21. |

### Phase 6 — Maintenance and genuine historical proof

| Task | My actions | Your actions | Done when / dependency |
|---|---|---|---|
| P23 — Maintainer handoff | Write concise setup/contribution and security-contact guidance appropriate to a personal project; document updates, token rotation, restore, model-price review, archive retention and shutdown. Define a monthly link/cost/security review and event-driven urgent patch process. Document scheduled automation only if actually configured. | Supply a preferred private security-contact route; own billing alerts and monthly review. Approve teardown if the hosted demo is no longer worth its cost. | A short maintenance checklist names the owner and how to retire the demo without losing release evidence. P21–P22. |
| P24 — Next-release replay and follow-through | On the next real release, replay a v1.0 archived run inside its preserved runtime in CI; keep current and old release evidence distinct. Reassess residual advisories and compare actual month-end spend with the projection. | Decide whether another release or optional capability adds portfolio value. | The literal previous-release criterion has real evidence; cost assumptions and open advisories have been revisited. Requires a later release, not just a new fixture label. |

## Dependency order and effort

```text
Source/publication hygiene + docs + replay lifecycle + security treatment
    -> hosted CI / fresh clone
    -> [live model pilot + paired evaluation]
    -> [frozen quant study + controls + sensitivity + research note]
    -> [accounts + storage + candidate deploy + restore + cost observation]
    -> final showcase / recording / downloadable evidence
    -> source and version freeze + reviewed baselines + final CI
    -> approved tag/deploy + rollback + portfolio publication
    -> maintenance and later-release replay
```

The three bracketed workstreams can proceed concurrently; presentation drafts can proceed alongside them. This is dependency parallelism, not a requirement to run additional agents. Source/skill/UI/model/research-analysis changes must finish **before** final replay baselines are generated. Docs-only presentation changes can follow without pretending earlier executable verification covered new code.

| Stage | Planning allowance for my work | Planning allowance for your work | Main uncertainty |
|---|---|---|---|
| Candidate/publication readiness | 1–2 focused workdays | 30–60 minutes | Replay lifecycle changes and first hosted CI |
| Live-model evidence | 1–2 focused workdays | 30–60 minutes plus account setup | Actual model behavior and authorized daily allowance |
| Quantitative research evidence | 1–3 focused workdays | 45–90 minutes | Study scope, deterministic analysis additions and result interpretation |
| Hosted setup and drills | 1–2 focused workdays | 45–90 minutes plus account verification | Service access, deployment integration, chosen retention |
| Portfolio presentation | 1–2 focused workdays | 60–120 minutes | Desired visual polish and recording revisions |
| Freeze/release/handoff | 0.5–1 focused workday | 30–60 minutes | Final CI and hosted rollback |

These are planning ranges for focused engineering effort, not measured remaining work or a promise about agent wall-clock speed. Allow roughly **two to three calendar weeks** once access is available, with a seven-day observation window running alongside the remaining work. Setup delays, daily evaluation limits and new failures can extend this. A reduced local/video showcase can be delivered earlier if the finish criteria are explicitly changed.

## Your action queue, in order

1. **Positioning:** equal AI-engineering and quant-research emphasis is confirmed. Supply a deadline and narrower target roles if useful.
2. **Publication identity:** choose the public GitHub repository under your account/organization, and grant access or create it yourself. Keep ownership and billing with you.
3. **Accounts and budgets:** enable Anthropic API, Fly, Neon and R2; install credentials securely; approve a bounded evaluation allowance, hosting ceiling and retention choices. Existing defaults are $1/run and $3/day for model spend, plus an approximately $25/month hosting target. Those defaults are not a promise about actual bills or authorization to spend more.
4. **Personal review:** evaluate a small sample of live outputs, approve the research protocol and interpretation, and perform a first-time README walkthrough. I prepare the material and handle technical fixes.
5. **Presentation:** provide your portfolio destination and preferred video host; record narration if wanted and approve public wording.
6. **Release:** approve the concrete release commit, residual risks and target deployment, then accept the hosted evidence. I can execute the technical release after that authorization.
7. **Ownership:** receive billing/security alerts and perform the brief ongoing maintenance review. I can help with future updates when requested; this session does not create unattended monitoring.

## Immediate next work I can do without account setup

Start P02–P05: prepare the reviewed source changes, reconcile active documentation, implement the replay release lifecycle, and prepare residual-advisory decisions. Draft P15–P18 presentation assets, the P07 model-evaluation protocol and P25 quantitative protocol in parallel with your account setup; begin P26 after the study design is frozen. Do not rerun all completed tests merely to recreate old evidence; run focused checks as changes land and the full release suite at the freeze.

The first reviewable handoff should contain a reconciled README/handoff/demo script, the release-safe replay approach, the quantitative study protocol, the first visitor-page/case-study draft, and a precise account/secret/budget checklist. Keep analysis additions tied to the study rather than expanding into a trading platform.

## Scope boundaries and open risks

| Item | Treatment for this finish |
|---|---|
| Full cost/concentration/capacity/regime red-team suite | P25/P26 add selected cost, delay and concentration analyses for the research note. They do not complete every external red-team procedure or automatically expand the model's review scope. Implement remaining analyses only if making that broader claim; missing analyses must remain `needs_evidence`. |
| Qualitative correctness of model prose | Manual sampled review plus disclosed limits. Structured numeric binding is not general semantic verification. |
| Simulated prices and proxy listing/EPS data | Clearly label in every public artifact. No real returns, investable alpha or real-world survivorship-completeness claims. |
| Broad load benchmark, telemetry dashboard, staging environment | Remain optional under ADR-0007/0009. Bounded hosted demo checks and a basic uptime/cost review are enough for this scope. |
| Real market prices, actual exchange calendar, production trading | The confirmed dual emphasis can demonstrate quant methodology through controlled simulations, but it cannot establish empirical equity alpha. A real-market study would require an explicitly expanded data/licensing/universe/calendar plan and honest limits on survivorship coverage; it need not require a paid vendor in every possible scope. Live trading and broker/order functionality remain out of scope. |
| OAuth, Claude.ai connector, multi-tenant SaaS UI | Optional. Prove the existing supported MCP/API-key client path first. |
| PyPI, custom domain, complex frontend rewrite | Optional distribution/branding choices, not blockers for a usable public project. |
| Retained blobs and administrative access | R2 retention protects objects under the configured rule; administrators can change policy. Avoid unconditional “tamper-proof” claims. Choose retention deliberately and test with the actual app token. |
| Advisory handling | Do not disable the scan or call the image vulnerability-free. Preserve dated evidence and track unpatched findings. |

## External facts checked for planning

Checked 2026-09-27; recheck before spending or deployment.

- The configured `claude-opus-5` is still documented but is now labelled legacy; its listed standard input/output prices are $5/$25 per million tokens, matching the current table. Retaining it is compatible with the existing decision, but availability and request behavior still need a live pilot. A model change needs a new baseline, not a silent substitution. [Anthropic Opus 5 documentation](https://platform.claude.com/docs/en/models/opus-5/overview).
- Neon restore history depends on plan; current provider material describes a Free limit of six hours and a change-history cap. Record the actual project window rather than assuming a multi-day backup policy. [Neon plan documentation](https://github.com/neondatabase/website/blob/main/content/docs/introduction/plans.md).
- R2 bucket locks prevent deletion and overwriting during retention, while the administrative configuration supports removing rules. Verify the app credential's restrictions and keep administration separate. [Cloudflare bucket-lock documentation](https://developers.cloudflare.com/r2/buckets/bucket-locks/).
- Fly documents stopped-machine storage charges and has announced pricing changes effective October 1, 2026. Auto-stop is a cost control, not a zero-cost guarantee; use the rates in effect for the planned launch. [Fly resource pricing](https://fly.io/docs/about/pricing/), [October pricing notice](https://fly.io/pricing-update/).

## Final acceptance checklist

- [ ] Public repository and exact release revision are available; hosted CI is green.
- [ ] A clean clone can run the offline demo and default evaluations.
- [ ] Current and historical replay checks preserve independent expected artifacts.
- [ ] Live-model pilot, accounting and paired evaluation evidence are published with appropriate limits.
- [ ] Quantitative protocol, data/methodology sheet, control/sensitivity results and research note reproduce from the release.
- [ ] Hosted demo, supported MCP client and authentication checks pass.
- [ ] Storage retention, restart, timed isolated restore and rollback are evidenced.
- [ ] A measured-period hosting cost record and monthly projection fit the agreed ceiling.
- [ ] README, handoff, demo script, case study and release notes agree.
- [ ] Screenshots, video, sample report and portfolio links work anonymously.
- [ ] Release artifacts, checksums, SBOM, scorecards and immutable image reference are downloadable.
- [ ] Residual risks have owners and review dates; no unsupported outcome claim remains.
- [ ] Alex signs off the public story and takes ownership of maintenance/billing.

Keep P24 open after this checklist closes. A finished first-release portfolio can have an explicit maintenance and next-release backlog.
