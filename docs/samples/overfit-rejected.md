# Run run_4301bfeec0024e938d06

**Status:** complete · **Decision:** reject
**Reason:** workflow complete
**Experiment:** `exp_13ab1b3ed629eda570eaf579` (trial 100 of `earnings-drift-search`)
**Hypothesis:** Companies whose EPS rose year over year outperform after the filing is accepted.
**Feature:** `eps_yoy_change` (acceptance timing) on `synthetic:v1:weak` (point_in_time universe)

> Prices are simulated with planted effects (ADR-0003). Results say nothing about real-world returns.

## Gate: reject
- Statistical threshold failed: Failed: deflated sharpe.

## Steps
| Step | Status | Attempts | Artifact |
|---|---|---|---|
| Hypothesis freeze | completed | 1 | `ev_232aaee78be24d044621dfa6` |
| Data acquisition | completed | 1 | `ev_b043ccbe40a9aad0839c3742` |
| Feature build | completed | 1 | `ev_ede242540a528584bb8be7aa` |
| Backtest | completed | 1 | `ev_06b9a5d8171cf06adce660b9` |
| Leakage audit | completed | 1 | `ev_29a171b7ff3cc023712afb34` |
| Statistical review | completed | 1 | `ev_400abc88a430f74085476d58` |
| Economic rationale review | completed | 1 | `ev_1143f48f71466cf2e4fae973` |
| Implementation review | completed | 1 | `ev_3776886da2579b5c4f294d93` |
| Research committee | completed | 1 | `ev_f36464be04662d22d804f857` |

## Statistics
- Observations: 1194; annualized Sharpe 1.48; Newey-West t 3.21
- Deflated Sharpe 0.755 across 100 trial(s); bootstrap CI [0.63, 2.38]

## Findings
- **[high] Failed: deflated sharpe** (Statistical review): probability the Sharpe beats the best of 100 null trials: 0.755 against a threshold of 0.950. Evidence: `ev_06b9a5d8171cf06adce660b9`
- **[medium] Committee decision: reject** (Research committee): demo-approver recorded 'reject' (gate recommended 'reject'): Demo decision following the gate (reject): Statistical threshold failed: Failed: deflated sharpe. Evidence: `ev_400abc88a430f74085476d58`
- **[info] Backtest completed** (Backtest): 1194 daily observations, annualized Sharpe 1.48 after 5 bps costs, execution 1 session(s) after the decision. Evidence: `ev_128c7b53dac0602f848311db`
- **[info] Prices are simulated** (Data acquisition): Prices in this dataset are simulated with planted effects (ADR-0003). Results say nothing about real-world returns. Evidence: `ev_128c7b53dac0602f848311db`
- **[info] Economic rationale review: supported** (Economic rationale review): A mechanism is stated and the measured relationship has the expected sign. Evidence: `ev_232aaee78be24d044621dfa6`, `ev_400abc88a430f74085476d58`
- **[info] Feature coverage** (Feature build): 'eps_yoy_change' (acceptance timing) has values for 2635 of 2635 eligible security-dates (100%) across 60 decision dates. Evidence: `ev_128c7b53dac0602f848311db`, `ev_bb7895cd783a82444b3652e7`
- **[info] Experiment frozen** (Hypothesis freeze): Experiment exp_13ab1b3ed629eda570eaf579 is trial 100 in research family 'earnings-drift-search'. Any change to it creates a new experiment and a new trial. Evidence: none
- **[info] Implementation review: feasible** (Implementation review): Implementation looks feasible as tested. Evidence: `ev_06b9a5d8171cf06adce660b9`, `ev_400abc88a430f74085476d58`
- **[info] No leakage detected** (Leakage audit): Every feature value has exactly one lineage row with inputs. Cited inputs must match the security, feature window and acceptance-known versions at the decision close. All 2635 feature values were recomputed from their cited inputs. All 5270 feature inputs were knowable at decision time. Trades execute 1 session(s) after the decision close (delay 30 minutes). The universe matched point-in-time listings on every decision date. Feature 'eps_yoy_change' does not use the prediction target. Evidence: `ev_06b9a5d8171cf06adce660b9`, `ev_bb7895cd783a82444b3652e7`, `ev_ede242540a528584bb8be7aa`

## Economic rationale review memo
Prices are simulated; no claim about real-world performance.

Scope: mechanism, measured_sign, timing_basis
Excluded from this review: full_red_team_signoff, cost_multiplier_stress, contributor_exclusion_stress, volatility_regime_stress, real_market_capacity, factor_crowding

### Facts
No statements supplied in this section.

### Calculations
- Mean information coefficient (/ic_mean): 0.061 [ev_400abc88a430f74085476d58]

### Assumptions
- The researcher states an economic mechanism in the frozen hypothesis. [ev_232aaee78be24d044621dfa6]

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
- The tested portfolio has the concentration recorded in the backtest evidence. [ev_06b9a5d8171cf06adce660b9]

### Calculations
- Mean turnover per rebalance (/turnover_mean): 0.37; Annualized cost drag (/cost_drag_annualized): 0.24% [ev_400abc88a430f74085476d58]

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
- An earlier review raised a material finding; its cited evidence and full finding remain in the run report. [ev_06b9a5d8171cf06adce660b9]

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
- demo-approver: **reject**: Demo decision following the gate (reject): Statistical threshold failed: Failed: deflated sharpe. (2026-09-27T23:13:08.179553Z)

## Audit trail
| # | Time | Step | Event | Actor |
|---|---|---|---|---|
| 164 | 2026-09-27T23:13:07.595691+00:00 | run | run_created | demo-researcher |
| 165 | 2026-09-27T23:13:07.599690+00:00 | run | run_status_changed | demo-researcher |
| 166 | 2026-09-27T23:13:07.603695+00:00 | Hypothesis freeze | step_started | demo-researcher |
| 167 | 2026-09-27T23:13:07.607695+00:00 | Hypothesis freeze | step_completed | demo-researcher |
| 168 | 2026-09-27T23:13:07.612696+00:00 | Data acquisition | step_started | demo-researcher |
| 169 | 2026-09-27T23:13:07.805904+00:00 | Data acquisition | step_completed | demo-researcher |
| 170 | 2026-09-27T23:13:07.809905+00:00 | Feature build | step_started | demo-researcher |
| 171 | 2026-09-27T23:13:07.857872+00:00 | Feature build | step_completed | demo-researcher |
| 172 | 2026-09-27T23:13:07.862873+00:00 | Backtest | step_started | demo-researcher |
| 173 | 2026-09-27T23:13:07.899384+00:00 | Backtest | step_completed | demo-researcher |
| 174 | 2026-09-27T23:13:07.903389+00:00 | Leakage audit | step_started | demo-researcher |
| 175 | 2026-09-27T23:13:07.972470+00:00 | Leakage audit | step_completed | demo-researcher |
| 176 | 2026-09-27T23:13:07.976468+00:00 | Statistical review | step_started | demo-researcher |
| 177 | 2026-09-27T23:13:08.037603+00:00 | Statistical review | step_completed | demo-researcher |
| 178 | 2026-09-27T23:13:08.042603+00:00 | Economic rationale review | step_started | demo-researcher |
| 179 | 2026-09-27T23:13:08.075121+00:00 | Economic rationale review | step_completed | demo-researcher |
| 180 | 2026-09-27T23:13:08.080630+00:00 | Implementation review | step_started | demo-researcher |
| 181 | 2026-09-27T23:13:08.114149+00:00 | Implementation review | step_completed | demo-researcher |
| 182 | 2026-09-27T23:13:08.119149+00:00 | Research committee | step_started | demo-researcher |
| 183 | 2026-09-27T23:13:08.167554+00:00 | Research committee | step_needs_review | demo-researcher |
| 184 | 2026-09-27T23:13:08.170553+00:00 | Research committee | run_status_changed | demo-researcher |
| 185 | 2026-09-27T23:13:08.183063+00:00 | Research committee | approval_recorded | demo-approver |
| 186 | 2026-09-27T23:13:08.187063+00:00 | Research committee | run_status_changed | demo-approver |
| 187 | 2026-09-27T23:13:08.188065+00:00 | Hypothesis freeze | step_reused | demo-approver |
| 188 | 2026-09-27T23:13:08.189063+00:00 | Data acquisition | step_reused | demo-approver |
| 189 | 2026-09-27T23:13:08.190063+00:00 | Feature build | step_reused | demo-approver |
| 190 | 2026-09-27T23:13:08.192640+00:00 | Backtest | step_reused | demo-approver |
| 191 | 2026-09-27T23:13:08.193641+00:00 | Leakage audit | step_reused | demo-approver |
| 192 | 2026-09-27T23:13:08.194640+00:00 | Statistical review | step_reused | demo-approver |
| 193 | 2026-09-27T23:13:08.195641+00:00 | Economic rationale review | step_reused | demo-approver |
| 194 | 2026-09-27T23:13:08.197640+00:00 | Implementation review | step_reused | demo-approver |
| 195 | 2026-09-27T23:13:08.200641+00:00 | Research committee | step_started | demo-approver |
| 196 | 2026-09-27T23:13:08.229153+00:00 | Research committee | step_completed | demo-approver |
| 197 | 2026-09-27T23:13:08.231928+00:00 | Research committee | run_status_changed | demo-approver |
