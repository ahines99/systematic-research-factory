# ADR-0008: Count trials at review time, and floor the Sharpe variance

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-015, RSF-021, RSF-040 (audit findings Q1 and Q5)

## Context
The deflated Sharpe ratio (DSR) is the system's defence against overfitting. It needs two inputs: the number of trials N, and the variance of Sharpe estimates across trials, V[SR]. The audit found two ways to defeat it.

1. **N was fixed when the experiment was frozen.** The first experiment in a family was never deflated by the variants frozen after it. Renaming the family reset N to 1.
2. **V[SR] came from the ledger whenever five or more results existed.** Near-duplicate variants have almost identical Sharpe ratios, so V[SR] fell to about zero and the DSR collapsed to the undeflated probabilistic Sharpe ratio. In the audit's example, 99 near-identical trials turned a DSR of 0.24 into 0.965.

Freezing N at freeze time was deliberate: it keeps the statistical-review artifact reproducible, so replays stay byte-identical.

## Decision
1. **Floor V[SR].** V[SR] is the larger of the ledger variance and the asymptotic sampling variance of a Sharpe estimate, (1 + SR²/2) / T. Trials that vary less than sampling noise cannot switch deflation off. Near-duplicates are then counted as independent trials, which is conservative.
2. **Report both counts, and gate on the review-time count.**
   - The statistical-review artifact keeps the freeze-time N, so replays stay reproducible.
   - At the committee step, the system recomputes the DSR at the number of *related trials that exist now*. That count is the larger of: trials in the same family, and trials anywhere that test the same feature on the same dataset.
   - If the review-time DSR fails the threshold, a `statistical_threshold` finding is added and the gate rejects.
   - The committee step is a judgment step, so it is not part of byte-identical replay.
3. **Families cannot be escaped by renaming.** "Same feature on the same dataset" counts across family names.

## Alternatives considered
- **An effective number of independent trials, by clustering correlated trials** (Bailey & López de Prado 2014, §3). This is more accurate but needs trial return series, not just Sharpe ratios. It's worth revisiting once the ledger stores return series.
- **Take N only at review time.** This is honest, but the statistical artifact would change whenever someone froze an unrelated variant, which breaks reproducibility.

## Consequences
- The "overfit rejected" demo now rejects whether or not its 99 prior variants are actually run.
- An experiment that looked fine as trial 1 can be rejected at committee once many variants exist. That's intended.
- Deflation can overcorrect when trials are genuinely correlated. That errs toward rejection, which is the safe direction.

## Revisit when
The ledger stores per-trial return series, so correlated trials can be clustered.
