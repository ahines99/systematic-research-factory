# Attack playbook

This file supports the `signal-red-team` Skill. Each attack below has: what it claims, how to test
it with the factory's tools, what failure looks like, what does *not* count as a refutation, and
when to raise its severity. All numbers come from tools and carry evidence IDs. `NEEDS_EVIDENCE`
is always an acceptable answer. A guess never is.

---

## 1. Look-ahead leakage
**Claim:** some input was not knowable at `decision_ts`, the target leaked into the features, or
the execution delay was not applied.

**Procedure**
1. `audit_leakage` for the run. Read every finding, not just the pass/fail flag.
2. Export the `build_features` lineage and run
   `python skills/point-in-time-research/scripts/check_pit_timestamps.py --json lineage.json`.
   Exit 1 is unrefuted. Rows flagged `no_inputs` or `naive_timestamp` mean the audit can't prove
   the timing, so the attack is not refuted.
3. Spot-check at least 5 filing-derived values: `get_filings_as_of(cik, as_of=decision_ts)` has to
   return the filing, and `get_filings_as_of(cik, as_of=decision_ts − 1 session)` has to return
   either no filing or the previous one.
4. Confirm the forward-return window starts at `decision_ts + execution_delay_minutes`.

**Failure signatures:** IC far above what's plausible for the signal type (for real-world
fundamental signals, a rebalance IC above ~0.10 deserves scrutiny; the synthetic worlds plant
stronger effects on purpose, so compare against the dataset's documented planted strength rather
than this rule of thumb); performance that collapses with a one-session delay (attack 5); returns
concentrated on the days *before* filing acceptance.

**Placebos:** a price-based feature such as `momentum_60_5` is not a clean placebo in these
datasets: the planted acceptance-day jump itself creates price momentum, so momentum can look as
strong as the EPS signal. Use the `synthetic:v1:null` world as the placebo instead.

**Not a refutation:** "the audit passed" when lineage rows have no inputs; "the spec says
`acceptance`" when no lineage was checked.

**Severity:** always `blocking`. Nothing overrides a confirmed leakage finding.

## 2. Restatement look-ahead
**Claim:** history uses the latest restated fact values (`timing_basis: latest_restated`, the XBRL
`frame` field, or the frames API) instead of the value known at the time.

**Procedure**
1. Read `timing_basis` from the frozen hypothesis (`run://{run_id}`).
2. Find a filer in the universe with a `10-K/A` or `10-Q/A`, or with a revised comparative.
   Call `get_filings_as_of` at an `as_of` just before and just after the amendment's acceptance.
   The value before must be the original.
3. Check that feature values for that filer change on the amendment's acceptance date, and not
   earlier.

**Failure signature:** accounting-quality signals (accruals, earnings quality) look much better
when built from restated data, because restatements are bad news that arrives later.

**Severity:** `blocking`.

## 3. Survivorship
**Claim:** the universe or the returns leave out names that died.

**Procedure**
1. The universe mode in the frozen spec must be `point_in_time`.
2. Compare `get_universe_as_of` at the first and last decision dates. Early-universe names that are
   missing later should exist, and should include delistings, not only renames.
3. In the backtest artifact, find positions in names that later delisted. Each must exit with a
   delisting return. No position may continue after delisting.

**Not a refutation:** a universe count that looks sensible but has no delisted names at all.

**Severity:** `blocking`.

## 4. Data snooping
**Claim:** the result is the best of many tries, some of which the ledger doesn't count.

**Procedure**
1. `get_ledger`: N for the family, the list of experiments, their freeze times, and how similar the
   specs are (small changes to horizon, filters, winsorization or feature definition).
2. `get_statistics`: DSR and the N it used. It must match the ledger.
3. Look for signs of search the ledger can't see:
   - The hypothesis was frozen *after* data covering the full test period was already available to
     the researcher, and the rationale is suspiciously specific (for example an unusual threshold
     or lookback with no economic reason).
   - The rationale was written after the result (HARKing): the statement explains quirks that only
     the result could reveal.
   - Several close variants in the family, with only the best one taken forward.
4. Fragility check: if a neighbouring spec already exists in the ledger (for example lookback ±25%),
   compare its statistics. A sharp peak at the chosen parameters is a sign of overfitting.

**Not a refutation:** a high t-statistic by itself. HLZ-style hurdles and the DSR exist because
t-statistics are what search inflates.

**Severity:** `high`. It is `blocking` if the DSR gate fails.

## 5. Execution delay sensitivity
**Claim:** the edge only exists if you trade at an unrealistically early time, which usually means
a hidden timing leak or a very short-lived microstructure effect.

**Procedure**
1. `run_backtest` variants: the frozen `execution_delay_minutes` plus 1 session, and plus 5
   sessions. Record each variant's ledger experiment ID.
2. `get_statistics` for each: IC and net Sharpe by delay.

**How to read it**
- Fundamental information typically decays over weeks. A gradual decline is expected.
- A **cliff at the first extra session** (for example IC 0.04 → ~0) means either (a) the signal
  depends on same-day information, so go back to attack 1, or (b) a real but very fast
  announcement effect whose capture needs execution the backtest can't guarantee. Either way it
  stays unrefuted until the cause is shown with evidence.

**Severity:** `high`. It is `blocking` if it is traced to a leak.

## 6. Cost sensitivity
**Claim:** net returns disappear at realistic costs.

**Procedure**
1. From the backtest artifact: gross and net returns, turnover, and the cost convention (one-way or
   round-trip, and per unit of what).
2. Break-even cost, **computed by the tool or taken from the artifact**. For costs charged as
   c × one-way turnover:
   c\* (bps) = 10⁴ × mean gross return per period / mean one-way turnover per period.
   Example to check the convention: gross 4 bps per day with 10% daily one-way turnover gives
   c\* = 40 bps.
3. `run_backtest` at 2× and 3× `transaction_cost_bps`.

**Refuted when** c\* ≥ 2× the assumed cost, and net Sharpe at 2× costs is > 0. Record whether it
still passes the statistical gates.

**Not a refutation:** comparing a round-trip break-even with a one-way cost assumption.

**Severity:** `high`. It drops to `medium` if the break-even is ≥ 3× the assumed cost.

## 7. Concentration in a few names (and dates)
**Claim:** a handful of securities or days produce the P&L.

**Procedure**
1. P&L contribution by security from the backtest artifact: the top-10 share of gross P&L and a
   Herfindahl index of the absolute contributions.
2. `get_statistics` on returns excluding the top 10 contributors, and excluding the top 1% of days.
3. Check whether the top contributors share one industry or one event, for example a single
   acquisition.

**Refuted when** the top 10 names are < ~30% of gross P&L, and the sign (and ideally the gates)
survive both exclusions.

**Severity:** `high`.

## 8. Regime dependence
**Claim:** the edge belongs to one period or market state.

**Procedure**
1. `get_statistics` by calendar year, and for the first half vs the second half of the sample.
2. Split by a volatility regime defined with **trailing** data only (for example trailing 63-day
   market volatility above or below its trailing median). A regime label that uses future data is
   itself a leak.
3. Check whether the edge decays over time. Published anomalies tend to weaken after publication
   (McLean & Pontiff 2016, "Does Academic Research Destroy Stock Return Predictability?").

**Refuted when** the sign is the same in most subperiods, no single year is more than ~40% of total
P&L, and there is no monotonic decay to zero.

**Severity:** `medium`. It is `high` if all of the edge sits in one regime.

## 9. Capacity
**Claim:** the strategy can't trade at meaningful capital without moving prices.

**Procedure**
1. Participation per trade = |shares traded| / 20-day average daily volume, at the capital stated
   in the implementation review. Volume comes from `get_prices_as_of`.
2. The share of trades above 5% and above 10% of ADV, and whether the P&L comes from the
   least liquid names.
3. When modelling impact, a square-root model (cost ∝ σ_daily × sqrt(Q / ADV)) is the usual
   practitioner form. Its coefficient is an assumption, and has to be recorded as one.

**Project caveat:** prices and volumes are simulated (ADR-0003). Report capacity as "a property of
the simulation" or `not_tested`.

**Severity:** `medium`.

## 10. Crowding
**Claim:** the signal is a relabelled known anomaly or factor, so the edge is either not new or is
shared with many others (crowding risk and correlated unwinds).

**Procedure**
1. Compare the economic rationale with well-known anomalies. Accruals (Sloan 1996) and
   post-earnings-announcement drift (Bernard & Thomas 1989) are the common ones for filing-derived
   signals.
2. If factor-return evidence exists: correlation and regression of the strategy's returns on
   standard factors. A high R² or a large, significant factor loading means crowding risk.
3. If no such evidence exists (the usual case here): `not_tested`, with a `NEEDS_EVIDENCE` note.

**Severity:** `medium`. It is `high` if the rationale depends on novelty that step 1 contradicts.

---

## Escalation summary
| Situation | Red-team recommendation |
|---|---|
| Any unrefuted `blocking` attack | reject |
| Any `high` or `blocking` attack that was `not_tested` | needs_more_evidence (list the exact tool calls) |
| Unrefuted `high`, all blocking attacks refuted | reject or needs_more_evidence, with reasoning |
| Only `medium` or `low` unrefuted | no objection, with conditions listed |
