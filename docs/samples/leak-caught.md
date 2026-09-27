# Run run_1664f30d9b47473e8668

**Status:** failed
**Reason:** leakage audit found blocking issues: lineage_semantics, knowledge_time
**Experiment:** `exp_ddf33066c7b4cffaa79864eb` (trial 2 of `earnings-drift`)
**Hypothesis:** Companies whose EPS rose year over year outperform after the filing is accepted.
**Feature:** `eps_yoy_change` (period_end timing) on `synthetic:v1` (point_in_time universe)

> Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.

## Gate: reject
- Blocking finding: Leakage: lineage semantics.
- Blocking finding: Leakage: knowledge time.

## Steps
| Step | Status | Attempts | Artifact |
|---|---|---|---|
| Hypothesis freeze | completed | 1 | `ev_9264f5393cf6c894b4339f72` |
| Data acquisition | completed | 1 | `ev_e32c0d5a276a8ba9027fc74c` |
| Feature build | completed | 1 | `ev_5d2d441fe6a070c8e3994a79` |
| Backtest | completed | 1 | `ev_c70a635fbaad5b4c4dc16aee` |
| Leakage audit | completed (LEAKAGE) | 1 | `ev_13f8aa0d6468d3dce720543e` |

## Findings
- **[blocking] Leakage: lineage semantics** (Leakage audit): Cited inputs must match the security, feature window and acceptance-known versions at the decision close. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_5d2d441fe6a070c8e3994a79`, `ev_c70a635fbaad5b4c4dc16aee`
- **[blocking] Leakage: knowledge time** (Leakage audit): 1242 feature inputs were not knowable at decision time. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_5d2d441fe6a070c8e3994a79`, `ev_c70a635fbaad5b4c4dc16aee`
- **[info] Backtest completed** (Backtest): 1194 daily observations, annualized Sharpe 3.33 after 5 bps costs, execution 1 session(s) after the decision. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Prices are simulated** (Data acquisition): Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing about real-world returns. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Feature coverage** (Feature build): 'eps_yoy_change' (period_end timing) has values for 2635 of 2635 eligible security-dates (100%) across 60 decision dates. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_d65f503f30d27fa8e2adebce`
- **[info] Experiment frozen** (Hypothesis freeze): Experiment exp_ddf33066c7b4cffaa79864eb is trial 2 in research family 'earnings-drift'. Any change to it creates a new experiment and a new trial. Evidence: none

## Audit trail
| # | Time | Step | Event | Actor |
|---|---|---|---|---|
| 37 | 2026-09-27T23:13:06.842870+00:00 | run | run_created | demo-researcher |
| 38 | 2026-09-27T23:13:06.845487+00:00 | run | run_status_changed | demo-researcher |
| 39 | 2026-09-27T23:13:06.850516+00:00 | Hypothesis freeze | step_started | demo-researcher |
| 40 | 2026-09-27T23:13:06.855539+00:00 | Hypothesis freeze | step_completed | demo-researcher |
| 41 | 2026-09-27T23:13:06.861074+00:00 | Data acquisition | step_started | demo-researcher |
| 42 | 2026-09-27T23:13:06.950658+00:00 | Data acquisition | step_completed | demo-researcher |
| 43 | 2026-09-27T23:13:06.955663+00:00 | Feature build | step_started | demo-researcher |
| 44 | 2026-09-27T23:13:07.006211+00:00 | Feature build | step_completed | demo-researcher |
| 45 | 2026-09-27T23:13:07.011809+00:00 | Backtest | step_started | demo-researcher |
| 46 | 2026-09-27T23:13:07.049951+00:00 | Backtest | step_completed | demo-researcher |
| 47 | 2026-09-27T23:13:07.054951+00:00 | Leakage audit | step_started | demo-researcher |
| 48 | 2026-09-27T23:13:07.140908+00:00 | Leakage audit | step_completed | demo-researcher |
| 49 | 2026-09-27T23:13:07.142416+00:00 | Leakage audit | run_status_changed | demo-researcher |
