---
name: financial-research-statistics
description: Interprets and challenges the statistical evidence for a systematic equity signal in the Systematic Research Factory. Covers multiple testing and the t above 3 hurdle, the deflated and probabilistic Sharpe ratios using the research ledger's trial count, Newey-West t-statistics for overlapping or serially correlated returns, block-bootstrap confidence intervals, IC and IC-IR, minimum track record length, and when not to trust a Sharpe ratio. Use when reading get_statistics output, deciding whether a run clears StatisticalThresholds (min_observations, min_newey_west_t, min_deflated_sharpe, bootstrap_confidence, require_ci_lower_above_zero), drafting the Statistical review section, answering "is this Sharpe ratio real?", or explaining a failed statistical gate. All arithmetic comes from tools, never from the model.
---

# Financial research statistics

## Execution modes

The external-agent procedure below uses MCP. In a tool-less judgment, `review_scope` lists
the assigned checks and exclusions; selected references are included in the actual prompt.
Review only the assigned claims using supplied statistics, including bootstrap metadata,
Newey-West lag and variance source. Missing material metadata for an assigned check requires
`needs_evidence=true`. Excluded stress tests remain unverified, never implicitly cleared.
For JSON calculations, return only `{metric:index}` placeholders with `metric_refs` selecting
cited artifact fields; code renders values and labels. Do not copy numeric prose from examples.

**Hard rule:** the model never computes a return, Sharpe ratio, t-statistic, p-value or confidence
interval. Every number comes from `get_statistics` (or another deterministic tool) and is quoted
with its evidence ID. If a number you need isn't in the tool output, say `NEEDS_EVIDENCE` and name
the tool call that would produce it. This Skill tells you how to *read* and *challenge* the
numbers. The formulas are in [references/formulas.md](references/formulas.md), so you can check
that the tool's inputs make sense.

## Procedure

1. **Context.** Call `get_run_report(run_id)` or read `run://{run_id}`. Record the `experiment_id`,
   `research_family`, `hold_days`, `execution_delay_minutes` and `transaction_cost_bps`.
2. **Trial count.** Call `get_ledger` or read `ledger://{research_family}`. Record N, the number of
   trials in the family, and confirm that `get_statistics` used the same N for the deflated Sharpe.
   Abandoned, failed and "bug-fix" variants still count: each re-frozen hypothesis is a trial.
3. **Statistics.** Call `get_statistics`. Record, with evidence IDs: number of observations,
   per-period and annualized Sharpe, skewness, kurtosis (and whether it is excess or not), the
   Newey-West t and its lag, the bootstrap method, block length, confidence level and interval,
   PSR, DSR with its N and V[SR], and the IC, IC-IR and IC t-statistic.
4. **Gate.** Apply the threshold table below. Every check that fails becomes a finding.
5. **Distrust checks.** Go through "When not to trust a Sharpe ratio". Each concern either cites
   evidence that clears it or becomes a finding or an open question.
6. **Write up** as facts (tool outputs) → assessment → findings. Every sentence with a number
   cites an `ev_<hex>`.

## Decision thresholds (from `StatisticalThresholds` in `research_factory/config.py`)

The values below are defaults. The live values are configuration: read them from
`project://policies` or the statistics output, and quote the values the run actually used.

| Config name | Default | Check | If it fails |
|---|---|---|---|
| `min_observations` | 252 | Number of return observations ≥ threshold (252 is about one year of daily data) | `NEEDS_EVIDENCE`: the sample is too short to estimate anything. Don't read the other statistics as evidence either way |
| `min_newey_west_t` | 3.0 | Newey-West t of mean return ≥ 3.0, **in the direction frozen in the hypothesis** | Failed statistical threshold (high severity; the gate rejects). Significance in the wrong direction is not a pass |
| `min_deflated_sharpe` | 0.95 | DSR ≥ 0.95. DSR is a *probability*, not a Sharpe ratio | Failed statistical threshold (the gate rejects) |
| `bootstrap_confidence` | 0.95 | Two-sided confidence level of the bootstrap interval | Not a test on its own; it sets the level of the next row |
| `require_ci_lower_above_zero` | True | The lower bound of the block-bootstrap interval of the annualized Sharpe ratio is > 0 | Failed statistical threshold (the gate rejects) |
| `max_delay_sharpe_decay` | 0.5 | Sharpe lost with one extra session of execution delay ≤ 50% | High-severity fragility finding (the gate asks for more evidence) |

**How findings map to the committee gate:** the deterministic rubric is authoritative. In
`research-committee`, any blocking finding leads to a reject recommendation, and any
`NEEDS_EVIDENCE` leads to needs_more_evidence. If the run report classifies a finding differently
from this table, the run report wins. Say that it differs.

Passing all the thresholds is **necessary, not sufficient.** The distrust checks and the red team
(`signal-red-team`) can still find a blocking problem.

## Multiple testing

- Every backtest you look at is a trial, whether or not it gets reported. With N independent
  trials of a zero-skill signal, the *largest* observed Sharpe grows with N, roughly with
  sqrt(2 ln N) standard errors.
- Harvey, Liu & Zhu (2016), "…and the Cross-Section of Expected Returns" (*Review of Financial
  Studies*), argue that a newly proposed factor should clear **t > 3.0**, not 2.0, because of how
  much factor mining has already been done. That is where `min_newey_west_t = 3.0` comes from. It
  is a rule of thumb, not a formal correction for this run's N.
- The deflated Sharpe ratio is the correction for *this* research family: it uses the ledger's N
  and the spread of Sharpe ratios across the family's trials.
- **What the ledger can't see:** choices tried in a notebook before freezing (feature definitions,
  winsorization levels, universe filters). If the rationale or the history suggests such search,
  write "trial count likely understated" as a risk. Don't adjust any number yourself.
- A robustness variant (different costs or delay) is a check, not a candidate. Promoting whichever
  variant looks best is data snooping.

## Deflated and probabilistic Sharpe ratios (what to check)

- **PSR(SR\*)** is the probability that the true Sharpe exceeds the benchmark SR\*, given the
  sample length, skewness and kurtosis. **DSR** is the PSR where SR\* is replaced by SR0, the
  Sharpe you would expect as the *maximum* of N zero-skill trials (Bailey & López de Prado 2014,
  "The Deflated Sharpe Ratio"). The formulas are in [references/formulas.md](references/formulas.md).
- Check that the tool fed them consistent inputs:
  - [ ] SR, SR0 and V[SR] are in **per-period** units (not annualized), and T counts periods.
  - [ ] Kurtosis in the formula is **non-excess** (3 for a normal distribution). Mixing it up with
    excess kurtosis changes the denominator.
  - [ ] N is stated twice: the trial count at freeze (`n_trials` in `get_statistics`) and the related trials that exist at review (the committee step reports both and gates on the larger). The formula needs N ≥ 2; with N = 1, DSR is PSR(0).
  - [ ] V[SR] never falls below the sampling variance (1 + SR²/2)/T, so near-duplicate trials cannot switch deflation off.
  - [ ] V[SR] is the variance of Sharpe ratios *across the family's trials*. If the tool used a
    fallback (for example the null sampling variance), say so under assumptions.
- High PSR(0) with low DSR is the classic sign of multiple testing: the result is significant on
  its own, but not given how many things were tried. The worked example in the formulas file shows
  exactly this case.

## Newey-West (serial correlation and overlapping holds)

- Use it when `hold_days > 1` and returns are measured daily (overlapping cohorts are
  autocorrelated by construction), when turnover is slow, or when returns show autocorrelation.
- [ ] The lag L is at least `hold_days − 1`. Watch for a default of L = 0 or 1 on a 21-day hold.
- [ ] If the Newey-West t is much *smaller* than the naive t = SR_per_period × sqrt(T), the naive
  number overstated the evidence. Report the Newey-West one.
- A useful identity: naive t ≈ annualized Sharpe × sqrt(years). A Sharpe of 1.0 needs about 9
  years to reach t = 3. Quote this to calibrate expectations, not as a calculation.

## Bootstrap confidence intervals

- An i.i.d. bootstrap destroys serial correlation and makes the interval too narrow. Expect a
  **block** or **stationary** bootstrap (Politis & Romano 1994) with a block length ≥ `hold_days`.
- [ ] Record the method, block length, number of resamples, seed and interval type (percentile,
  BCa). If any of them is missing: `NEEDS_EVIDENCE`.
- Say which statistic was bootstrapped: mean return and Sharpe have different intervals.

## IC and IC-IR

- IC_t is the cross-sectional (usually Spearman rank) correlation between the signal at t and the
  forward return over the holding window. Report its mean, standard deviation, IC-IR = mean / sd,
  and its t-statistic.
- Typical scale: a mean monthly IC of 0.02–0.05 can be economically meaningful across a broad
  universe (fundamental law: IR ≈ IC × sqrt(breadth), Grinold 1989). An IC above ~0.10 on a
  fundamental signal is a **leakage red flag**, not a success.
- Daily ICs with multi-day forward returns overlap, so their t-statistic needs Newey-West or
  non-overlapping sampling.

## When not to trust a Sharpe ratio

| Concern | Evidence to ask for | Red flag |
|---|---|---|
| Short sample | observations, `min_track_record_length` from `get_statistics` (against SR\* = 0) | observations < MinTRL at 95% against SR\* = 0 (and against SR0) |
| Negative skew, fat tails | skewness, kurtosis, worst days | skew < −1 or kurtosis > 10 (option-like payoffs: the Sharpe hides crash risk) |
| Overlapping holds / autocorrelation | Newey-West lag, autocorrelations | annualizing by sqrt(252) with positive autocorrelation understates volatility (Lo 2002, "The Statistics of Sharpe Ratios") |
| Costs | gross vs net, turnover, cost assumption | net Sharpe < 50% of gross, or a break-even cost close to realistic costs |
| Stale or smoothed prices | return autocorrelation, zero-return days | illiquid names drive the Sharpe |
| A few names or dates | contribution concentration (red team) | top 10 names or top 1% of days carry most of the P&L |
| Regime | Sharpe by subperiod | sign flips between halves of the sample |
| Survivorship or look-ahead | `audit_leakage` | any unresolved leakage finding makes every statistic invalid |
| Simulated prices | ADR-0003 label | results show the pipeline recovered the planted effect, not real-world alpha |

## Worked example (short)

Five years of daily data (T = 1260), annualized Sharpe 1.5, skew −0.5, kurtosis 6, N = 20 trials,
cross-trial standard deviation of annualized Sharpe 0.5. From
[references/formulas.md](references/formulas.md): naive t = 3.35, Newey-West t = 3.05 with
ρ1..ρ3 = 0.10, 0.05, 0.02 and L = 3 (**passes**, but 2.97 at the automatic L = 7, so it's
fragile), PSR(0) = 0.9994, SR0 = 0.95 annualized,
**DSR = 0.884 < 0.95 (fails)**. The recommendation is not "approve": the result doesn't survive the
family's search. The minimum track record against SR0 is about 9.5 years.

## Output format for the Statistical review
```
Statistical review — run <run_id> (experiment <experiment_id>, family <family>, N=<n> trials [ev_…])
Facts: <each statistic with value and ev_…>
Threshold checks: <config name: value vs threshold → pass/fail [ev_…]>
Distrust checks: <concern → cleared [ev_…] | finding | NEEDS_EVIDENCE (tool + args)>
Findings: <blocking / non-blocking / NEEDS_EVIDENCE, each with ev_…>
Assumptions: <e.g. V[SR] fallback used, trial count may be understated>
```
