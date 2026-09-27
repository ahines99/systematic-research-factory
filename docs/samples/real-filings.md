# Run run_8a269a114df045e9976e

**Status:** complete · **Decision:** reject
**Reason:** workflow complete
**Experiment:** `exp_7b56aaeb7ba08c640311924e` (trial 1 of `earnings-drift-edgar`)
**Hypothesis:** Companies whose EPS rose year over year outperform after the filing is accepted.
**Feature:** `eps_yoy_change` (acceptance timing) on `edgar-semi:v1` (point_in_time universe)

> Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.

## Gate: reject
- Statistical threshold failed: Failed: newey west t.

## Steps
| Step | Status | Attempts | Artifact |
|---|---|---|---|
| Hypothesis freeze | completed | 1 | `ev_8304f6ff933016ba93b19e4f` |
| Data acquisition | completed | 1 | `ev_ec8f6207605549480cebd5d4` |
| Feature build | completed | 1 | `ev_04b20e571861873da5c16082` |
| Backtest | completed | 1 | `ev_578252e0f791e4bc2677543b` |
| Leakage audit | completed | 1 | `ev_57a488f92278b5aca4d7a2bd` |
| Statistical review | completed | 1 | `ev_3c4a652d7179fdc0d022c854` |
| Economic rationale review | completed | 1 | `ev_bd71d3c9e7572ef6cc6d6a04` |
| Implementation review | completed | 1 | `ev_98a194e04a8b930a1d08bb80` |
| Research committee | completed | 1 | `ev_7e1d67a56c5baeb651e2f538` |

## Statistics
- Observations: 1194; annualized Sharpe 1.20; Newey-West t 2.55
- Deflated Sharpe 0.996 across 1 trial(s); bootstrap CI [0.30, 2.13]

## Findings
- **[high] Failed: newey west t** (Statistical review): HAC t-statistic of mean return: 2.551 against a threshold of 3.000. Evidence: `ev_578252e0f791e4bc2677543b`
- **[medium] Committee decision: reject** (Research committee): demo-approver recorded 'reject' (gate recommended 'reject'): Demo decision following the gate (reject): Statistical threshold failed: Failed: newey west t. Evidence: `ev_3c4a652d7179fdc0d022c854`
- **[info] Backtest completed** (Backtest): 1194 daily observations, annualized Sharpe 1.20 after 5 bps costs, execution 1 session(s) after the decision. Evidence: `ev_7023d6bd3eef2447dfd14162`
- **[info] Prices are simulated** (Data acquisition): Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing about real-world returns. Evidence: `ev_7023d6bd3eef2447dfd14162`
- **[info] Economic rationale review: supported** (Economic rationale review): A mechanism is stated and the measured relationship has the expected sign. Evidence: `ev_3c4a652d7179fdc0d022c854`, `ev_8304f6ff933016ba93b19e4f`
- **[info] Feature coverage** (Feature build): 'eps_yoy_change' (acceptance timing) has values for 2245 of 2291 eligible security-dates (98%) across 60 decision dates. Evidence: `ev_7023d6bd3eef2447dfd14162`, `ev_d347cd43dbe1dc085d35b636`
- **[info] Experiment frozen** (Hypothesis freeze): Experiment exp_7b56aaeb7ba08c640311924e is trial 1 in research family 'earnings-drift-edgar'. Any change to it creates a new experiment and a new trial. Evidence: none
- **[info] Implementation review: feasible** (Implementation review): Implementation looks feasible as tested. Evidence: `ev_3c4a652d7179fdc0d022c854`, `ev_578252e0f791e4bc2677543b`
- **[info] No leakage detected** (Leakage audit): Every feature value has exactly one lineage row with inputs. Cited inputs must match the security, feature window and acceptance-known versions at the decision close. All 2245 feature values were recomputed from their cited inputs. All 4490 feature inputs were knowable at decision time. Trades execute 1 session(s) after the decision close (delay 30 minutes). The universe matched point-in-time listings on every decision date. Feature 'eps_yoy_change' does not use the prediction target. Evidence: `ev_04b20e571861873da5c16082`, `ev_578252e0f791e4bc2677543b`, `ev_d347cd43dbe1dc085d35b636`

## Economic rationale review memo
Prices are simulated; no claim about real-world performance.

Scope: mechanism, measured_sign, timing_basis
Excluded from this review: full_red_team_signoff, cost_multiplier_stress, contributor_exclusion_stress, volatility_regime_stress, real_market_capacity, factor_crowding

### Facts
No statements supplied in this section.

### Calculations
- Mean information coefficient (/ic_mean): 0.056 [ev_3c4a652d7179fdc0d022c854]

### Assumptions
- The researcher states an economic mechanism in the frozen hypothesis. [ev_8304f6ff933016ba93b19e4f]

### Risks and counterarguments
No statements supplied in this section.

### Recommendation
supported

### Open questions
None supplied for the assigned scope.

### Red-team attacks
No full red-team signoff was performed in this targeted review.

### Dissent
None recorded.

### Decision record
Left blank by the reviewer; human decisions appear under Approvals.

## Implementation review memo
Prices are simulated; no claim about real-world performance.

Scope: cost_drag, execution_delay, portfolio_concentration
Excluded from this review: full_red_team_signoff, cost_multiplier_stress, contributor_exclusion_stress, volatility_regime_stress, real_market_capacity, factor_crowding

### Facts
- The tested portfolio has the concentration recorded in the backtest evidence. [ev_578252e0f791e4bc2677543b]

### Calculations
- Mean turnover per rebalance (/turnover_mean): 0.48; Annualized cost drag (/cost_drag_annualized): 0.30% [ev_3c4a652d7179fdc0d022c854]

### Assumptions
No statements supplied in this section.

### Risks and counterarguments
No statements supplied in this section.

### Recommendation
feasible

### Open questions
None supplied for the assigned scope.

### Red-team attacks
No full red-team signoff was performed in this targeted review.

### Dissent
None recorded.

### Decision record
Left blank by the reviewer; human decisions appear under Approvals.

## Research committee memo
Prices are simulated; no claim about real-world performance.

Scope: gate_consistency, findings, memo, recorded_dissent
Excluded from this review: full_red_team_signoff, cost_multiplier_stress, contributor_exclusion_stress, volatility_regime_stress, real_market_capacity, factor_crowding

### Facts
No statements supplied in this section.

### Calculations
No statements supplied in this section.

### Assumptions
No statements supplied in this section.

### Risks and counterarguments
- An earlier review raised a material finding; its cited evidence and full finding remain in the run report. [ev_578252e0f791e4bc2677543b]

### Recommendation
reject

### Open questions
None supplied for the assigned scope.

### Red-team attacks
No full red-team signoff was performed in this targeted review.

### Dissent
None recorded.

### Decision record
Left blank by the reviewer; human decisions appear under Approvals.

## Approvals
- demo-approver: **reject**: Demo decision following the gate (reject): Statistical threshold failed: Failed: newey west t. (2026-09-27T23:13:09.001279Z)

## Audit trail
| # | Time | Step | Event | Actor |
|---|---|---|---|---|
| 199 | 2026-09-27T23:13:08.237441+00:00 | run | run_created | demo-researcher |
| 200 | 2026-09-27T23:13:08.240040+00:00 | run | run_status_changed | demo-researcher |
| 201 | 2026-09-27T23:13:08.245041+00:00 | Hypothesis freeze | step_started | demo-researcher |
| 202 | 2026-09-27T23:13:08.251039+00:00 | Hypothesis freeze | step_completed | demo-researcher |
| 203 | 2026-09-27T23:13:08.254040+00:00 | Data acquisition | step_started | demo-researcher |
| 204 | 2026-09-27T23:13:08.449384+00:00 | Data acquisition | step_completed | demo-researcher |
| 205 | 2026-09-27T23:13:08.453384+00:00 | Feature build | step_started | demo-researcher |
| 206 | 2026-09-27T23:13:08.519292+00:00 | Feature build | step_completed | demo-researcher |
| 207 | 2026-09-27T23:13:08.523315+00:00 | Backtest | step_started | demo-researcher |
| 208 | 2026-09-27T23:13:08.572931+00:00 | Backtest | step_completed | demo-researcher |
| 209 | 2026-09-27T23:13:08.577931+00:00 | Leakage audit | step_started | demo-researcher |
| 210 | 2026-09-27T23:13:08.741625+00:00 | Leakage audit | step_completed | demo-researcher |
| 211 | 2026-09-27T23:13:08.746626+00:00 | Statistical review | step_started | demo-researcher |
| 212 | 2026-09-27T23:13:08.828616+00:00 | Statistical review | step_completed | demo-researcher |
| 213 | 2026-09-27T23:13:08.833817+00:00 | Economic rationale review | step_started | demo-researcher |
| 214 | 2026-09-27T23:13:08.872822+00:00 | Economic rationale review | step_completed | demo-researcher |
| 215 | 2026-09-27T23:13:08.876822+00:00 | Implementation review | step_started | demo-researcher |
| 216 | 2026-09-27T23:13:08.917912+00:00 | Implementation review | step_completed | demo-researcher |
| 217 | 2026-09-27T23:13:08.924429+00:00 | Research committee | step_started | demo-researcher |
| 218 | 2026-09-27T23:13:08.985278+00:00 | Research committee | step_needs_review | demo-researcher |
| 219 | 2026-09-27T23:13:08.988278+00:00 | Research committee | run_status_changed | demo-researcher |
| 220 | 2026-09-27T23:13:09.006279+00:00 | Research committee | approval_recorded | demo-approver |
| 221 | 2026-09-27T23:13:09.010282+00:00 | Research committee | run_status_changed | demo-approver |
| 222 | 2026-09-27T23:13:09.012283+00:00 | Hypothesis freeze | step_reused | demo-approver |
| 223 | 2026-09-27T23:13:09.014283+00:00 | Data acquisition | step_reused | demo-approver |
| 224 | 2026-09-27T23:13:09.015283+00:00 | Feature build | step_reused | demo-approver |
| 225 | 2026-09-27T23:13:09.016283+00:00 | Backtest | step_reused | demo-approver |
| 226 | 2026-09-27T23:13:09.018283+00:00 | Leakage audit | step_reused | demo-approver |
| 227 | 2026-09-27T23:13:09.020283+00:00 | Statistical review | step_reused | demo-approver |
| 228 | 2026-09-27T23:13:09.021284+00:00 | Economic rationale review | step_reused | demo-approver |
| 229 | 2026-09-27T23:13:09.022285+00:00 | Implementation review | step_reused | demo-approver |
| 230 | 2026-09-27T23:13:09.026863+00:00 | Research committee | step_started | demo-approver |
| 231 | 2026-09-27T23:13:09.060373+00:00 | Research committee | step_completed | demo-approver |
| 232 | 2026-09-27T23:13:09.062374+00:00 | Research committee | run_status_changed | demo-approver |
