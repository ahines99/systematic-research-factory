# Formulas and a worked example

This file supports the `financial-research-statistics` Skill. It is for **checking** the tool
outputs and for building reference tests (RSF-021). The model does not use it to compute run
statistics: those come from `get_statistics`.

Notation: r_t is the per-period strategy return (daily unless stated), t = 1..T. r̄ is the sample
mean, σ̂ the sample standard deviation, SR = r̄ / σ̂ the **per-period** Sharpe (excess of the risk-free
rate if the strategy is not self-financing; a dollar-neutral long-short is usually treated as
excess already). γ3 is skewness and γ4 is **non-excess** kurtosis (3 for a normal distribution).
Φ is the standard normal CDF and Φ⁻¹ its inverse.

## 1. Sharpe ratio and naive t-statistic
- Annualized SR = SR × sqrt(periods per year), e.g. sqrt(252). This scaling assumes i.i.d.
  returns. With positive autocorrelation it overstates the annual Sharpe (Lo 2002, "The Statistics
  of Sharpe Ratios").
- Naive t of the mean = r̄ / (σ̂ / sqrt(T)) = SR × sqrt(T) ≈ SR_annual × sqrt(years).

## 2. Newey-West t-statistic (Newey & West 1987)
Sample autocovariances, for l = 0..L:

  γ̂_l = (1/T) Σ_{t=l+1..T} (r_t − r̄)(r_{t−l} − r̄)

Long-run variance, with Bartlett weights w_l = 1 − l/(L+1):

  Ω̂ = γ̂_0 + 2 Σ_{l=1..L} w_l γ̂_l

  t_NW = r̄ / sqrt(Ω̂ / T)

Writing ρ̂_l = γ̂_l / γ̂_0 gives t_NW = t_naive / sqrt(1 + 2 Σ w_l ρ̂_l), up to the T vs T−1
normalization.

Choosing the lag: at least `hold_days − 1` for overlapping h-day holds. A common automatic choice is
L = floor(4 (T/100)^(2/9)), which is 7 for T = 1260. Take the larger of the two.

## 3. Probabilistic Sharpe ratio
Against a benchmark SR\* (per period):

  PSR(SR\*) = Φ( (SR − SR\*) · sqrt(T − 1) / sqrt(1 − γ3·SR + ((γ4 − 1)/4)·SR²) )

For normal returns (γ3 = 0, γ4 = 3) the denominator is sqrt(1 + SR²/2), the standard large-sample
variance of the Sharpe estimator. Negative skew and fat tails make the denominator larger and PSR
lower. PSR, like DSR, treats returns as *independent* (though not normal). With autocorrelated
returns, check it against the Newey-West t.

## 4. Deflated Sharpe ratio (Bailey & López de Prado 2014, "The Deflated Sharpe Ratio")
Expected maximum Sharpe among N zero-skill trials (per period):

  SR0 = sqrt(V[SR]) · ( (1 − γ) · Φ⁻¹(1 − 1/N) + γ · Φ⁻¹(1 − 1/(N·e)) ),  γ ≈ 0.5772156649 (Euler–Mascheroni)

  DSR = PSR(SR0)

- N is the ledger's trial count for the research family. It needs N ≥ 2. With N = 1 there is
  nothing to deflate, and DSR = PSR(0).
- V[SR] is the variance of the per-period Sharpe estimates *across the N trials*.
- The bracketed term is the expected maximum of N standard normals. It grows slowly:

  | N | 2 | 5 | 10 | 20 | 50 | 100 | 1000 |
  |---|---|---|---|---|---|---|---|
  | E[max] factor | 0.520 | 1.193 | 1.575 | 1.901 | 2.276 | 2.531 | 3.255 |

## 5. Minimum track record length (Bailey & López de Prado 2012, "The Sharpe Ratio Efficient Frontier")
The number of observations needed for PSR(SR\*) ≥ 1 − α:

  MinTRL = 1 + (1 − γ3·SR + ((γ4 − 1)/4)·SR²) · ( Φ⁻¹(1 − α) / (SR − SR\*) )²

It is only defined for SR > SR\*. Units are periods: divide by 252 for years of daily data.

## 6. Information coefficient
- IC_t = Spearman rank correlation, across securities i, of signal s_{i,t} and forward return
  r_{i,t→t+h}.
- IC-IR = mean(IC_t) / sd(IC_t), per period. To annualize, multiply by sqrt(periods per year).
- t(mean IC) = IC-IR × sqrt(n_periods), valid for *non-overlapping* periods. With daily ICs and
  h > 1, use Newey-West with L ≥ h − 1, or sample every h days.
- Fundamental law (Grinold 1989): IR ≈ IC × sqrt(breadth). This is a heuristic for scale, not a test.

## 7. Bootstrap confidence interval
- Stationary bootstrap (Politis & Romano 1994): resample blocks whose lengths are geometric with
  mean b, wrapping around the end of the sample. Recompute the statistic on each of B resamples.
- Percentile interval at confidence c: the (1−c)/2 and (1+c)/2 quantiles of the resampled
  statistics. `require_ci_lower_above_zero` checks the lower quantile.
- b ≥ `hold_days`. A common starting point is b ≈ T^(1/3). Record B, b, the seed and the interval type.

---

## Worked example (computed and checked)

Inputs, all hypothetical: T = 1260 daily returns (5 years); annualized Sharpe 1.5; γ3 = −0.5;
γ4 = 6 (non-excess); first three return autocorrelations 0.10, 0.05, 0.02 (zero beyond); N = 20
trials in the family; cross-trial standard deviation of *annualized* Sharpe 0.5.

**Per-period inputs**
- SR = 1.5 / sqrt(252) = 0.094491
- sqrt(V[SR]) = 0.5 / sqrt(252) = 0.031497, V[SR] = 0.00099206

**Naive and Newey-West t (L = 3)**
- t_naive = 0.094491 × sqrt(1260) = 0.094491 × 35.4965 = **3.354**
- Weights 0.75, 0.50, 0.25. 1 + 2(0.75·0.10 + 0.50·0.05 + 0.25·0.02) = 1 + 2(0.105) = 1.21. sqrt = 1.10
- t_NW = 3.354 / 1.10 = **3.049**, which passes `min_newey_west_t = 3.0` narrowly.
- **The result depends on the lag.** With the automatic lag L = 7 and the same autocorrelations,
  the weights on lags 1–3 become 0.875, 0.75 and 0.625: 1 + 2(0.1375) = 1.275, sqrt = 1.1292, and
  t_NW = **2.970**, which **fails**. A result that passes at one defensible lag and fails at
  another is fragile. Report both, and always check which lag the tool used.

**Non-normality denominator**
- 1 − γ3·SR + ((γ4 − 1)/4)·SR² = 1 + 0.5 × 0.094491 + 1.25 × 0.0089286 = 1 + 0.047246 + 0.011161 = 1.058406
- sqrt = 1.028789
- sqrt(T − 1) = sqrt(1259) = 35.4824

**PSR against zero**
- z = 0.094491 × 35.4824 / 1.028789 = **3.2589**, PSR(0) = Φ(3.2589) = **0.99944**

**Deflated Sharpe**
- Φ⁻¹(1 − 1/20) = Φ⁻¹(0.95) = 1.644854
- Φ⁻¹(1 − 1/(20e)) = Φ⁻¹(0.981606) = 2.088110
- E[max] factor = 0.422784 × 1.644854 + 0.577216 × 2.088110 = **1.900708**
- SR0 = 0.031497 × 1.900708 = **0.059867** per day (0.9504 annualized)
- z = (0.094491 − 0.059867) × 35.4824 / 1.028789 = **1.1942**, DSR = Φ(1.1942) = **0.8838**

This **fails** `min_deflated_sharpe = 0.95`.

**Minimum track record at 95% (Φ⁻¹(0.95) = 1.644854)**
- Against SR\* = 0: 1 + 1.058406 × (1.644854 / 0.094491)² = **321.7** days (about 1.3 years). Satisfied.
- Against SR\* = SR0: 1 + 1.058406 × (1.644854 / 0.034624)² = **2389.6** days (about 9.5 years). Not satisfied.

**IC example.** A mean monthly IC of 0.03 with sd 0.12 over 60 months gives IC-IR = 0.25 per month
(0.87 annualized) and t = 0.25 × sqrt(60) = **1.94**. That is economically plausible but
statistically weak on its own.

**Reading.** On its own the strategy looks significant (t_NW 3.05 at L = 3, but only 2.97 at
L = 7; PSR(0) 0.9994). Given 20 trials
with this spread of outcomes, the best trial would be expected to reach an annualized Sharpe of
about 0.95 by luck alone, and the evidence that 1.5 beats that is only about 88% (below the 95%
bar). Gate outcome: blocking statistical finding.

### Reproduction (standard library only, for reference tests)
```python
from math import sqrt, e
from statistics import NormalDist

N01 = NormalDist()
g = 0.5772156649015329
T, sr, sk, ku, N = 1260, 1.5 / sqrt(252), -0.5, 6.0, 20
sqrtV = 0.5 / sqrt(252)
den = sqrt(1 - sk * sr + (ku - 1) / 4 * sr**2)
psr = lambda s0: N01.cdf((sr - s0) * sqrt(T - 1) / den)
sr0 = sqrtV * ((1 - g) * N01.inv_cdf(1 - 1 / N) + g * N01.inv_cdf(1 - 1 / (N * e)))
print(round(psr(0.0), 5), round(sr0, 6), round(psr(sr0), 4))  # 0.99944 0.059867 0.8838
```
