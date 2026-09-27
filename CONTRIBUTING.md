# Contributing and maintaining

Use Python 3.12–3.14 and the committed uv lockfile. Keep a short checkout path on Windows. Work on a branch, explain the concrete behavior change, and preserve independent evidence rather than updating expectations to hide failures.

```bash
uv sync --locked --all-extras
uv run --no-sync ruff check src tests scripts
uv run --no-sync ruff format --check src tests scripts
uv run --no-sync mypy
uv run --no-sync pytest
uv run --no-sync rsf eval --provider rules
```

CI separately verifies PostgreSQL, distribution installation, container smoke/restart, dependency and image audits, and historical numerical comparison. Do not use a paid provider in routine tests. A source, dependency or Skill change can make old execution manifests incompatible; retain old baselines and their selected environments. Read [the replay follow-up](docs/audits/2026-09-27/ci-followup.md) before changing that behavior.

Keep the research protocol/results immutable after observation. A new experimental design needs a new labeled protocol and outputs. Do not claim empirical alpha from simulated prices or live-model uplift from scripted tests. Changes affecting budgets, public authentication, evidence retention or approval policy require explicit reasoning and regression coverage in the PR.

Maintenance owner: Alex Hines. Check CI/security alerts weekly, review spend during active use, and review dependencies/base images monthly or sooner for relevant advisories. Before an update, preserve the last release digest and evidence; after it, run CI and bounded smoke/recovery checks. If maintenance stops, disable paid/provider access, revoke app/viewer credentials, stop Fly machines, export verified database/evidence backups, and schedule resource deletion only after the agreed retention and recovery requirements are met. Keep the static GitHub showcase available. Detailed commands live in the runbook; do not automatically delete retained evidence.
