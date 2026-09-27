# Run run_b88246820b6d49d0b86d

**Status:** failed
**Reason:** leakage audit found blocking issues: universe
**Experiment:** `exp_2a58263e05a26e6ad16c5bf0` (trial 3 of `earnings-drift`)
**Hypothesis:** Companies whose EPS rose year over year outperform after the filing is accepted.
**Feature:** `eps_yoy_change` (acceptance timing) on `synthetic:v1` (current_constituents universe)

> Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.

## Gate: reject
- Blocking finding: Leakage: universe.

## Steps
| Step | Status | Attempts | Artifact |
|---|---|---|---|
| Hypothesis freeze | completed | 1 | `ev_dc035369da14d10622172e3f` |
| Data acquisition | completed | 1 | `ev_f165ea40deeab86eeae9eac6` |
| Feature build | completed | 1 | `ev_74fb7eb7a401cae5565a1a79` |
| Backtest | completed | 1 | `ev_e3f1b0758c3ecaa6d79eb455` |
| Leakage audit | completed (LEAKAGE) | 1 | `ev_56f538d22ce0c0931d95132f` |

## Findings
- **[blocking] Leakage: universe** (Leakage audit): On 53 decision dates the universe differed from point-in-time listings (securities that were listed then were excluded, or unlisted ones included): survivorship bias. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_74fb7eb7a401cae5565a1a79`, `ev_e3f1b0758c3ecaa6d79eb455`
- **[info] Backtest completed** (Backtest): 1194 daily observations, annualized Sharpe 2.42 after 5 bps costs, execution 1 session(s) after the decision. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Prices are simulated** (Data acquisition): Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing about real-world returns. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Feature coverage** (Feature build): 'eps_yoy_change' (acceptance timing) has values for 2463 of 2463 eligible security-dates (100%) across 60 decision dates. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_d65f503f30d27fa8e2adebce`
- **[info] Experiment frozen** (Hypothesis freeze): Experiment exp_2a58263e05a26e6ad16c5bf0 is trial 3 in research family 'earnings-drift'. Any change to it creates a new experiment and a new trial. Evidence: none

## Audit trail
| # | Time | Step | Event | Actor |
|---|---|---|---|---|
| 51 | 2026-09-27T23:13:07.148932+00:00 | run | run_created | demo-researcher |
| 52 | 2026-09-27T23:13:07.151931+00:00 | run | run_status_changed | demo-researcher |
| 53 | 2026-09-27T23:13:07.155931+00:00 | Hypothesis freeze | step_started | demo-researcher |
| 54 | 2026-09-27T23:13:07.162931+00:00 | Hypothesis freeze | step_completed | demo-researcher |
| 55 | 2026-09-27T23:13:07.165931+00:00 | Data acquisition | step_started | demo-researcher |
| 56 | 2026-09-27T23:13:07.247148+00:00 | Data acquisition | step_completed | demo-researcher |
| 57 | 2026-09-27T23:13:07.251685+00:00 | Feature build | step_started | demo-researcher |
| 58 | 2026-09-27T23:13:07.291151+00:00 | Feature build | step_completed | demo-researcher |
| 59 | 2026-09-27T23:13:07.296156+00:00 | Backtest | step_started | demo-researcher |
| 60 | 2026-09-27T23:13:07.330581+00:00 | Backtest | step_completed | demo-researcher |
| 61 | 2026-09-27T23:13:07.335095+00:00 | Leakage audit | step_started | demo-researcher |
| 62 | 2026-09-27T23:13:07.399619+00:00 | Leakage audit | step_completed | demo-researcher |
| 63 | 2026-09-27T23:13:07.400619+00:00 | Leakage audit | run_status_changed | demo-researcher |
