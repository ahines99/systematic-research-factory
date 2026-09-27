# Frozen simulation study: earnings timing and research controls

Protocol v1, frozen 2026-09-27 before running this new study. No paid model or live market data is used. The exact protocol file hash is recorded in every result bundle. Changes after inspecting results require a new protocol and must keep the original results.

## Question and scope

How do fiscal-period look-ahead and repeated experimentation distort an earnings-growth strategy, and can the workflow distinguish deliberately invalid inputs from valid point-in-time research? This is a controlled simulation study, not a claim of empirical equity alpha. EPS year-over-year growth is not an analyst-consensus earnings surprise or an empirical PEAD estimate.

## Frozen design

- Synthetic world: 50 securities, 2019-01-02 through 2023-12-29, 2017 filing warm-up, six exits, five IPOs and ten attempted restatements; existing generator and price process unchanged.
- Development seeds: 101 and 102. Evaluation seeds: integers 200 through 219 inclusive. No optimization or selection of the best seed is permitted; all seeds and variants are reported.
- Primary evaluation window: 2022-01-03 through 2023-12-29. Development period: 2019-06-03 through 2021-12-31, evaluated only on development seeds. Historical filings remain available as feature warm-up.
- Paired controls: no planted jump/drift (`jump_beta=0`, `drift_gamma=0`) and the existing planted process (`0.04`, `0.03`). Shared seeds couple the remaining random inputs for paired comparisons.
- Signal: EPS year-over-year change available at the decision close. Universe: point-in-time listed securities. Rank long top 20%, short bottom 20%; 0.5 gross exposure each side, constant weights between rebalances. Rebalance/hold every 20 weekday sessions; trade at the next session close; charge five basis points per unit turnover. No risk-free subtraction or market hedge beyond dollar neutrality.
- Both controls run clean acceptance timing and the intentionally invalid period-end variant. Run the leakage audit for both; invalid results are diagnostic counterfactuals and must never be described as implementable strategies.
- Frozen sensitivities on planted evaluation worlds: costs 0/10/25 bps (baseline 5); one additional execution session; quantiles 10%/30% (baseline 20%); holding periods 10/40 sessions (baseline 20). Include period-end variant: ten configurations total per world, counting the baseline. No best-configuration selection.
- Statistics: annualized mean/std Sharpe (252 sessions), annualized mean and volatility, compounded simulated cumulative return, maximum drawdown including starting wealth 1, mean one-way gross turnover, arithmetic cost drag, IC and average/max per-name target exposure. Exposure concentration is not P&L attribution or a complete concentration stress test.
- Use existing Newey-West, DSR and circular block-bootstrap implementations. Bootstrap 2,000 samples, 95% interval, block length equal to holding period, existing fixed bootstrap seed. Show DSR at ten configurations for comparability; also expose sensitivity to 1/100 assumed trials without treating those assumed counts as an actual ledger search. Independent seeds are replications, not extra optimized strategy variants.
- Report per-seed data and cross-seed medians/ranges and paired differences; include Wilson 95% intervals on gate/audit outcome frequencies. With only 20 evaluation worlds, rates are imprecise. No claim of precisely calibrated statistical power, false-positive rate, or general error control.
- Record every configuration and seed in the study result ledger. This ledger is a study artifact, not the interactive application's persisted experiment ledger. The research harness reuses deterministic calculation/audit code; it does not run model reviews or manufacture committee approvals.

## Interpretation rules

Report every planned result, including unexpectedly weak planted signals or leaky variants that do not improve returns. Do not change thresholds or seeds to obtain a preferred outcome. Split timing and seed evaluation are safeguards against post-hoc tuning, but the generator's design is already known and this is not an independent validation of a real market hypothesis.

The generator standardizes event shocks using its simulated event population. That is part of the data-generating process, not an estimator available to a real strategy; it limits realism. Weekdays include exchange holidays. Borrow fees, liquidity, dynamic weight drift costs, final liquidation costs and capacity are not modelled. The study does not complete the full external red-team procedure.

## Publication and reproduction

Run `uv run python scripts/research_study.py --out docs/research/results`. The runner writes raw JSON, a flat CSV and standalone SVG/PNG charts. A command with `--development` uses only the two development seeds and writes separately; it is not reported as the evaluation study. The published note must identify protocol, runner, source, dataset and dependency identities and disclose any deviations from this protocol.
