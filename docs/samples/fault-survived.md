# Run run_c3d12d18656147559cd1

**Status:** complete · **Decision:** approve
**Reason:** workflow complete
**Experiment:** `exp_a53230e1527e387521f1ead7` (trial 1 of `earnings-drift`)
**Hypothesis:** Companies whose EPS rose year over year outperform after the filing is accepted.
**Feature:** `eps_yoy_change` (acceptance timing) on `synthetic:v1` (point_in_time universe)

> Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.

## Gate: approve
- No blocking, statistical or evidence findings.

## Steps
| Step | Status | Attempts | Artifact |
|---|---|---|---|
| Hypothesis freeze | completed | 1 | `ev_8c4ecae1c9f09a1fd571f9b8` |
| Data acquisition | completed | 2 | `ev_5e2f9d5c0db77683cca94477` |
| Feature build | completed | 1 | `ev_9304f3f751675205decc849a` |
| Backtest | completed | 1 | `ev_0de5751faf57d1197e91df51` |
| Leakage audit | completed | 1 | `ev_979a53db4fadca2e9f59afa3` |
| Statistical review | completed | 1 | `ev_db04778265d6690c7e553790` |
| Economic rationale review | completed | 1 | `ev_f6fc27dd05e93ca77045250d` |
| Implementation review | completed | 1 | `ev_fdab3407e528a83d79a63795` |
| Research committee | completed | 1 | `ev_dadb54822d728e243de55b03` |

## Statistics
- Observations: 1194; annualized Sharpe 2.54; Newey-West t 5.00
- Deflated Sharpe 1.000 across 1 trial(s); bootstrap CI [1.60, 3.49]

## Findings
- **[info] Backtest completed** (Backtest): 1194 daily observations, annualized Sharpe 2.54 after 5 bps costs, execution 1 session(s) after the decision. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Prices are simulated** (Data acquisition): Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing about real-world returns. Evidence: `ev_d65f503f30d27fa8e2adebce`
- **[info] Economic rationale review: supported** (Economic rationale review): A mechanism is stated and the measured relationship has the expected sign. Evidence: `ev_8c4ecae1c9f09a1fd571f9b8`, `ev_db04778265d6690c7e553790`
- **[info] Feature coverage** (Feature build): 'eps_yoy_change' (acceptance timing) has values for 2635 of 2635 eligible security-dates (100%) across 60 decision dates. Evidence: `ev_235f58b0b2d432638aa34404`, `ev_d65f503f30d27fa8e2adebce`
- **[info] Experiment frozen** (Hypothesis freeze): Experiment exp_a53230e1527e387521f1ead7 is trial 1 in research family 'earnings-drift'. Any change to it creates a new experiment and a new trial. Evidence: none
- **[info] Implementation review: feasible** (Implementation review): Implementation looks feasible as tested. Evidence: `ev_0de5751faf57d1197e91df51`, `ev_db04778265d6690c7e553790`
- **[info] No leakage detected** (Leakage audit): Every feature value has exactly one lineage row with inputs. Cited inputs must match the security, feature window and acceptance-known versions at the decision close. All 2635 feature values were recomputed from their cited inputs. All 5270 feature inputs were knowable at decision time. Trades execute 1 session(s) after the decision close (delay 30 minutes). The universe matched point-in-time listings on every decision date. Feature 'eps_yoy_change' does not use the prediction target. Evidence: `ev_0de5751faf57d1197e91df51`, `ev_235f58b0b2d432638aa34404`, `ev_9304f3f751675205decc849a`
- **[info] Deflated Sharpe holds at today's trial count** (Research committee): 3 related trials exist now (3 in family 'earnings-drift', 3 testing eps_yoy_change on synthetic:v1); at that count the deflated Sharpe is 1.000 (threshold 0.95). At freeze it was 1.000 over 1. Evidence: `ev_db04778265d6690c7e553790`
- **[info] Committee decision: approve** (Research committee): demo-approver recorded 'approve' (gate recommended 'approve'): Demo decision following the gate (approve): No blocking, statistical or evidence findings. Evidence: `ev_db04778265d6690c7e553790`
- **[info] All statistical thresholds met** (Statistical review): Annualized Sharpe 2.54, Newey-West t 5.00, deflated Sharpe 1.000 over 1 trial(s), bootstrap 95% CI [1.60, 3.49]. Evidence: `ev_0de5751faf57d1197e91df51`

## Economic rationale review memo
Prices are simulated; no claim about real-world performance.

Scope: mechanism, measured_sign, timing_basis
Excluded from this review: full_red_team_signoff, cost_multiplier_stress, contributor_exclusion_stress, volatility_regime_stress, real_market_capacity, factor_crowding

### Facts
No statements supplied in this section.

### Calculations
- Mean information coefficient (/ic_mean): 0.110 [ev_db04778265d6690c7e553790]

### Assumptions
- The researcher states an economic mechanism in the frozen hypothesis. [ev_8c4ecae1c9f09a1fd571f9b8]

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
- The tested portfolio has the concentration recorded in the backtest evidence. [ev_0de5751faf57d1197e91df51]

### Calculations
- Mean turnover per rebalance (/turnover_mean): 0.37; Annualized cost drag (/cost_drag_annualized): 0.24% [ev_db04778265d6690c7e553790]

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
- No material findings were raised by earlier steps. [ev_db04778265d6690c7e553790]

### Calculations
No statements supplied in this section.

### Assumptions
No statements supplied in this section.

### Risks and counterarguments
No statements supplied in this section.

### Recommendation
approve

### Open questions
None supplied for the assigned scope.

### Red-team attacks
No full red-team signoff was performed in this targeted review.

### Dissent
None recorded.

### Decision record
Left blank by the reviewer; human decisions appear under Approvals.

## Approvals
- demo-approver: **approve**: Demo decision following the gate (approve): No blocking, statistical or evidence findings. (2026-09-27T23:13:09.722948Z)

## Audit trail
| # | Time | Step | Event | Actor |
|---|---|---|---|---|
| 233 | 2026-09-27T23:13:09.066881+00:00 | run | run_created | demo-researcher |
| 234 | 2026-09-27T23:13:09.070886+00:00 | run | run_status_changed | demo-researcher |
| 235 | 2026-09-27T23:13:09.074886+00:00 | Hypothesis freeze | step_started | demo-researcher |
| 236 | 2026-09-27T23:13:09.079394+00:00 | Hypothesis freeze | step_completed | demo-researcher |
| 237 | 2026-09-27T23:13:09.083063+00:00 | Data acquisition | step_started | demo-researcher |
| 238 | 2026-09-27T23:13:09.085073+00:00 | Data acquisition | step_retry | demo-researcher |
| 239 | 2026-09-27T23:13:09.142517+00:00 | Data acquisition | step_started | demo-researcher |
| 240 | 2026-09-27T23:13:09.263386+00:00 | Data acquisition | step_completed | demo-researcher |
| 241 | 2026-09-27T23:13:09.268386+00:00 | Feature build | step_started | demo-researcher |
| 242 | 2026-09-27T23:13:09.334084+00:00 | Feature build | step_completed | demo-researcher |
| 243 | 2026-09-27T23:13:09.340111+00:00 | Backtest | step_started | demo-researcher |
| 244 | 2026-09-27T23:13:09.374038+00:00 | Backtest | step_completed | demo-researcher |
| 245 | 2026-09-27T23:13:09.379543+00:00 | Leakage audit | step_started | demo-researcher |
| 246 | 2026-09-27T23:13:09.477146+00:00 | Leakage audit | step_completed | demo-researcher |
| 247 | 2026-09-27T23:13:09.483159+00:00 | Statistical review | step_started | demo-researcher |
| 248 | 2026-09-27T23:13:09.567859+00:00 | Statistical review | step_completed | demo-researcher |
| 249 | 2026-09-27T23:13:09.572889+00:00 | Economic rationale review | step_started | demo-researcher |
| 250 | 2026-09-27T23:13:09.604689+00:00 | Economic rationale review | step_completed | demo-researcher |
| 251 | 2026-09-27T23:13:09.610200+00:00 | Implementation review | step_started | demo-researcher |
| 252 | 2026-09-27T23:13:09.643849+00:00 | Implementation review | step_completed | demo-researcher |
| 253 | 2026-09-27T23:13:09.648358+00:00 | Research committee | step_started | demo-researcher |
| 254 | 2026-09-27T23:13:09.705077+00:00 | Research committee | step_needs_review | demo-researcher |
| 255 | 2026-09-27T23:13:09.707083+00:00 | Research committee | run_status_changed | demo-researcher |
| 256 | 2026-09-27T23:13:09.727660+00:00 | Research committee | approval_recorded | demo-approver |
| 257 | 2026-09-27T23:13:09.732950+00:00 | Research committee | run_status_changed | demo-approver |
| 258 | 2026-09-27T23:13:09.734545+00:00 | Hypothesis freeze | step_reused | demo-approver |
| 259 | 2026-09-27T23:13:09.736224+00:00 | Data acquisition | step_reused | demo-approver |
| 260 | 2026-09-27T23:13:09.738261+00:00 | Feature build | step_reused | demo-approver |
| 261 | 2026-09-27T23:13:09.739790+00:00 | Backtest | step_reused | demo-approver |
| 262 | 2026-09-27T23:13:09.741314+00:00 | Leakage audit | step_reused | demo-approver |
| 263 | 2026-09-27T23:13:09.741314+00:00 | Statistical review | step_reused | demo-approver |
| 264 | 2026-09-27T23:13:09.744369+00:00 | Economic rationale review | step_reused | demo-approver |
| 265 | 2026-09-27T23:13:09.745898+00:00 | Implementation review | step_reused | demo-approver |
| 266 | 2026-09-27T23:13:09.749903+00:00 | Research committee | step_started | demo-approver |
| 267 | 2026-09-27T23:13:09.780439+00:00 | Research committee | findings_superseded | demo-approver |
| 268 | 2026-09-27T23:13:09.787439+00:00 | Research committee | step_completed | demo-approver |
| 269 | 2026-09-27T23:13:09.789441+00:00 | Research committee | run_status_changed | demo-approver |
