# Operations, delivery, packaging, and documentation audit

Auditor 4 of the five-agent audit; 2026-09-27; repository commit `91e3023`. Read-only source inspection plus isolated builds/reproductions under `var/audit-2026-09-27/ops-build/`. No deployments, keys, paid model calls, external messages, or source modifications.

## Assessment

The repository has substantial implemented delivery infrastructure, but the claim that only owner-account actions remain is false. There is a concrete Dockerfile build blocker, incomplete package resources, a broken release instruction, an image scan/deployment provenance gap, and incomplete historical replay validation. These are engineering work, not missing owner credentials.

## Verified inventory

- Hatchling project at version 0.1.0 with Python >=3.12, `rsf` entry point, uv lock, dev group and PostgreSQL/S3/OTel extras.
- Docker multi-stage build installs a locked non-editable application, includes PostgreSQL and S3 dependencies, intends UID10001 execution, and uses a digest-pinned Python base. Compose supplies PostgreSQL16, durable DB/blob volumes, migration/demo/serve commands.
- Fly configuration specifies rolling deploy, migration release command, TLS, autostop, 512MB machine, Neon/R2 environment wiring and model budget.
- CI specifies Python3.12/3.13 lint/types/tests/coverage, PostgreSQL16 repository tests, 30 rules evaluations, and pip-audit. Release specifies version guard, tests/evals, build, image scan, SBOM, GHCR push, GitHub release, Fly deploy, health smoke.
- Extensive docs include setup, runbook, threat model, architecture, 9 ADRs, 83-ticket roadmap, demo script and go-live review.
- Offline `python -m uv build --offline --out-dir var/audit-2026-09-27/ops-build` succeeded for sdist and a wheel built from that sdist. Wheel has 80 entries, 10 Skill entries, the EDGAR compressed snapshot, and four migration entries.
- Git status stayed clean. Root auditor established no remote/tags and independently ran source checks/tests/PostgreSQL suite; those results are not repeated here.

## Findings and acceptance criteria

### O1 — P1: Dockerfile contains literal backslash-n and cannot execute its user creation step

Evidence: `Dockerfile:16` is one physical line: `RUN useradd --create-home --uid 10001 rsf \n    && mkdir ...`. Bytes/repr confirm a literal backslash followed by `n`, not a continuation/newline. POSIX `shlex.split` converts the useradd segment into `useradd --create-home --uid 10001 rsf n`; the extra positional login causes useradd usage failure before mkdir. `tests/test_supply_chain.py:54` only checks regex/text markers, so it passes this defective Dockerfile. Container builds are absent from PR CI (`.github/workflows/ci.yml`) and first attempted on release.

Verification level: malformed bytes and POSIX argument parsing verified. Full Docker build could not run because Docker is absent; the predicted useradd failure follows directly from the malformed command.

Work: replace the literal escape with a genuine continuation or a single valid shell command. Add an actual build and container/compose smoke to CI before release. Acceptance: build on Linux, confirm UID10001, migration, demo, HTTP and PostgreSQL/blob persistence after restart. Reclassify RSF-061 as engineering repair plus environment verification, not only owner work.

### O2 — P2: Release deploys a newly built image, not the scanned/SBOM image

Evidence: `.github/workflows/release.yml:43` builds/loads the GHCR-tagged image; lines 49–59 scan it and generate its SBOM; line65 pushes it; line78 runs `flyctl deploy --remote-only` without passing that image/digest. `docs/deployment.md:27` explicitly endorses the independent rebuild. No digest continuity check connects those images. Docker uses a mutable uv image tag (`Dockerfile:6`) and unpinned build dependency (`pyproject.toml:2`); identical source alone does not prove identical build output.

Verification level: workflow wiring verified; no release executed. This is a missing guarantee, not evidence that two images already differ.

Work: deploy the same immutable scanned image digest, or scan the exact Fly-built image and publish the corresponding SBOM before rollout. Acceptance: release record maps commit -> image digest -> scan/SBOM -> running Fly digest; these match.

### O3 — P2: Built distributions omit files required by their bundled CLI/tests

Evidence: `pyproject.toml:48` packages only research_factory plus forced Skills; `pyproject.toml:55` omits evals, examples, Dockerfile, uv.lock, .env.example and IMPLEMENTATION_HANDOFF.md from sdist. CLI defaults to cwd-relative `evals/golden` (`src/research_factory/cli.py:329`). Extracted-wheel execution in an isolated cwd, using the existing Python3.12 dependency environment and explicit wheel PYTHONPATH, exits1 with `FileNotFoundError: evals\\golden`. The wheel and sdist have zero golden files. This also affects the wheel-only Docker image if its `rsf eval` command is used.

Selected tests shipped in the extracted sdist (`tests/test_docs.py`, `tests/test_supply_chain.py`, `tests/test_demo_cli_evals.py`) produced **12 failed, 11 passed**, all failures from missing auxiliary files. Missing groups were directly enumerated from the tar/zip; the wheel's Skills, snapshot and migrations are present.

Work: decide supported distribution CLI behavior, package default golden cases with resource-based lookup, and include fixtures/examples/metadata needed by shipped source tests (or explicitly scope tests to checkout-only and exclude them consistently). Acceptance: installed wheel runs `rsf demo` and default `rsf eval` from an unrelated cwd; source distribution can run its shipped test suite without hidden checkout files; CI builds and validates both.

### O4 — P2: Documented version-bump procedure produces a stale lockfile and fails release

Evidence: `docs/deployment.md:31` instructs bumping only pyproject and __init__, then committing/tagging. `uv.lock:1846` includes the project metadata/version, while `.github/workflows/release.yml:30` uses `uv sync --locked`. In a scratch copy of the project metadata and original lock, changing project version0.1.0 ->1.0.0 then running `uv lock --check --offline` exited1: `The lockfile at uv.lock needs to be updated`.

Work: include `uv lock` and lock validation in the release preparation instructions and commit the updated lock alongside both version fields; update the changelog to a dated release entry. Acceptance: follow the documented steps from current0.1.0 and pass `uv lock --check --offline` and release verify before tagging.

### O5 — P2: CI does not test replay of an archive from an earlier release

Evidence: roadmap RSF-077 is marked done (`docs/ROADMAP.md:171`) but explicitly requires earlier-release archive + recorded code version + CI replay (`docs/ROADMAP.md:683`). Both replay tests create fresh current-code runs first (`tests/test_demo_cli_evals.py:28`, `:259`). The committed manifest reports `Windows-AMD64-py3.14-numpy2.5.3`, while CI is Ubuntu3.12/3.13 (`.github/workflows/ci.yml:18`, `:22`); committed artifact equality runs only when platform strings match (`tests/test_demo_cli_evals.py:54` and `:58`). Thus GitHub CI checks scenario outcomes against the old manifest but only compares artifact bytes between two current-code executions. An arithmetic regression could preserve outcomes, change both current outputs identically, and pass.

Verification level: verified test/manifest/CI control flow; no historical artifact corruption alleged. Code/config provenance and replay-provider issues are separately covered by the workflow auditor.

Work: preserve a release or explicitly labeled baseline archive including data, expected artifacts, code/dependency/config provenance; execute against a compatible pinned platform in CI. Acceptance: a deliberate deterministic numerical change fails stored-artifact comparison, while a clean build reproduces every supported archived scenario. Reopen RSF-077 and RSF-082's stored-library acceptance until this exists.

### O6 — P2: Deployment smoke proves liveness only

Evidence: release smoke only curls `/healthz` (`.github/workflows/release.yml:84`). That handler unconditionally returns ok/version (`src/research_factory/http_app.py:132`), with no DB read, blob retrieval, MCP handshake or authenticated workflow verification. The Docker and Fly probes use the same endpoint. Startup builds services/migrates, so some initial failures are detected, but later dependency failure or broken client behavior can still look healthy.

Work: retain cheap liveness and add a bounded readiness/release smoke that checks DB, retrieves known evidence, initializes MCP, and verifies a guest demo plus authorized read/action against the deployed version. Acceptance: database/blob unavailability or incompatible MCP behavior makes deployment verification fail; test stays free of model spend. This is a validation gap, not an observed hosted outage.

### O7 — P2 documentation/work tracking: Completion and owner-only claims overstate evidence

Evidence: `docs/go-live-review.md:5`, `docs/ROADMAP.md:5`, README status and CHANGELOG state all locally verifiable code/config is complete and remaining work requires owner accounts. O1–O5 disprove that. RSF-075 is done at `docs/ROADMAP.md:169` although its done-when requires CI image scanning and release SBOM publication (`:674`), neither exercised in this no-remote/no-release repository. RSF-077 and part of082 are also prematurely done as above.

Owner checklist (`docs/ROADMAP.md:48` onward) omits acceptance details still required by ticket bodies: measured idle hosting cost <=about $25/month (`:621`), and a tested rollback (`:687`), not merely deploying/tagging. The go-live review requires the first release before tagging1.0.0, while 1.0.0 is the first release; sequencing should distinguish pre-tag verification from post-deployment release signoff.

Work: update claims after repairs, explicitly track code complete vs locally verified vs hosted/CI verified, include cost measurement and rollback drill, and define a concrete first-release sequence. Acceptance: every done ticket points to evidence satisfying its full done-when; remaining engineering work is separate from authorized owner-account work. Do not mark optional scope as required by accident.

## Secondary hardening / low-priority observations

- Actions use release tags, not immutable commit SHAs; uv uses a release tag, not a digest. Python base is digest-pinned and uv.lock pins app dependencies. Describe this accurately; consider SHA/digest pinning with deliberate updates rather than claiming all build inputs are immutable.
- Release verify runs tests/evals but not lint, mypy, dependency audit or PostgreSQL CI, and does not require the tag commit to have successful main-branch CI. Existing no-remote state also cannot provide branch/tag protection evidence. Require all release checks or enforce an approved tested-commit path.
- Release has workflow-wide contents/packages write permissions and no release concurrency declaration. Narrow job token scopes and serialize production deployments when setting up GitHub; these are hardening, not demonstrated exploits.
- `docs/architecture.md:148` says later experiments never change an earlier review, contradicting review-time committee trial counting elsewhere in that document and ADR0008. Clarify freeze-time statistic vs committee recheck; the quantitative auditor has related findings.
- The root auditor performed a fresh strict pip-audit of the locked all-extras production dependency export: exit0, no known vulnerabilities (see dependency-audit.json). This is package-advisory coverage, not a container image scan. Live Claude compatibility and account-dependent provider configuration need their assigned checks.

## Remaining owner/account work (after engineering repairs)

1. GitHub remote/public repository setup, push, branch protections and real CI results (RSF004/060); release environment and deploy credentials.
2. Real model baseline and with/without Skills A/B evidence (034/039), under an explicit approved spend cap.
3. Container build/compose verification on Docker-equipped Linux (061), now preceded by O1 repair.
4. Neon/Fly/R2 provisioning, secret configuration, R2 retention/lock controls and permission validation (065/067); record chosen restore retention and actual idle costs.
5. Deploy/seed demo/authenticated client checks (079), timed scratch restore and replay drill (068), tested rollback (078).
6. Version+lock+changelog update; first scanned-image release and deployment evidence; final go-live review and demo recording (052/078/080).

Still intentionally skipped: separate0.1 release053, licensed prices081, hosted OAuth083, OTel070, dashboards072, optional load test076. These decisions need not be reversed to complete the accepted v1 scope.

## Reproduction artifacts and limits

- `ops-build/systematic_research_factory-0.1.0.tar.gz` and `.whl`: built successfully offline.
- `ops-build/wheel/`: extracted wheel used for cwd-independent eval reproduction.
- `ops-build/sdist/`: extracted source distribution used for the 23 selected tests (12failed/11passed).
- `ops-build/version-bump/`: isolated stale-lock reproduction.
- Docker was unavailable. No hosted CI, provider account, release, deployment, restore/rollback drill or vulnerability network scan was performed here. Findings distinguish inspected configuration from executed behavior.
