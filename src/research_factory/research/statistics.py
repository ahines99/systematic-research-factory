"""Statistical review (RSF-021). Deterministic; thresholds come from configuration.

References:
* Newey & West (1987): heteroskedasticity- and autocorrelation-consistent variance.
* Bailey & López de Prado (2014), "The Deflated Sharpe Ratio": probabilistic Sharpe ratio
  (PSR) and the expected maximum Sharpe ratio across N independent trials.
* Harvey, Liu & Zhu (2016): t > 3 as a multiple-testing-aware hurdle.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from statistics import NormalDist
from typing import Any

import numpy as np
import numpy.typing as npt

from ..config import StatisticalThresholds

FloatArray = npt.NDArray[np.float64]
EULER_GAMMA = 0.5772156649015329
PERIODS_PER_YEAR = 252
BOOTSTRAP_SEED = 20260923
_N = NormalDist()


def sharpe(x: FloatArray) -> float:
    """Per-period Sharpe ratio (mean / population standard deviation)."""
    sd = float(np.std(x))
    return float(np.mean(x)) / sd if sd > 0 else 0.0


def moments(x: FloatArray) -> tuple[float, float]:
    """Skewness and (non-excess) kurtosis, population estimators."""
    d = x - x.mean()
    m2 = float(np.mean(d**2))
    if m2 == 0:
        return 0.0, 3.0
    return float(np.mean(d**3)) / m2**1.5, float(np.mean(d**4)) / m2**2


def newey_west_lags(n: int) -> int:
    """Newey-West (1994) plug-in: floor(4 (n/100)^(2/9))."""
    return int(4 * (n / 100) ** (2 / 9))  # floor, as the value is positive


def newey_west_t(x: FloatArray, lags: int) -> float:
    """t-statistic of the mean using a Bartlett-kernel long-run variance."""
    n = len(x)
    if n < 2:
        return 0.0
    d = x - x.mean()
    lrv = float(np.dot(d, d)) / n
    for lag in range(1, min(lags, n - 1) + 1):
        weight = 1.0 - lag / (lags + 1.0)
        lrv += 2.0 * weight * float(np.dot(d[lag:], d[:-lag])) / n
    if lrv <= 0:
        return 0.0
    return float(x.mean()) / math.sqrt(lrv / n)


def probabilistic_sharpe(sr: float, sr_benchmark: float, n: int, skew: float, kurt: float) -> float:
    """PSR: probability that the true per-period Sharpe exceeds ``sr_benchmark``."""
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if n < 2 or denom <= 0:
        return 0.0
    return _N.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom))


def null_sharpe_variance(sr: float, n: int) -> float:
    """Asymptotic variance of a per-period Sharpe estimate: (1 + SR^2 / 2) / T."""
    return (1 + 0.5 * sr**2) / max(n, 1)


def min_track_record_length(sr: float, skew: float, kurt: float, confidence: float = 0.95) -> float | None:
    """Periods needed for PSR(0) to reach ``confidence`` (Bailey & López de Prado 2012)."""
    if sr <= 0:
        return None
    z = _N.inv_cdf(confidence)
    return 1 + (1 - skew * sr + (kurt - 1) / 4 * sr**2) * (z / sr) ** 2


def deflated_sharpe_at(stats: dict[str, Any], n_trials: int) -> float:
    """Recompute the deflated Sharpe from a statistics artifact at a different trial count."""
    return probabilistic_sharpe(
        stats["sharpe_per_period"],
        expected_max_sharpe(n_trials, stats["var_sr"]),
        stats["n_obs"],
        stats["skew"],
        stats["kurtosis"],
    )


def expected_max_sharpe(n_trials: int, var_sr: float) -> float:
    """Expected maximum of ``n_trials`` per-period Sharpe estimates under the null."""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    return math.sqrt(var_sr) * (
        (1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
        + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e))
    )


def block_bootstrap_sharpe_ci(
    x: FloatArray, block: int, samples: int, confidence: float, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """Circular block bootstrap percentile CI of the annualized Sharpe ratio."""
    n = len(x)
    if n < 2:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    block = max(1, min(block, n))
    n_blocks = -(-n // block)
    offsets = np.arange(block)
    stats = np.empty(samples)
    for b in range(samples):
        starts = rng.integers(0, n, n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        stats[b] = sharpe(x[idx]) * math.sqrt(PERIODS_PER_YEAR)
    alpha = (1 - confidence) / 2
    return float(np.quantile(stats, alpha)), float(np.quantile(stats, 1 - alpha))


@dataclass
class Check:
    name: str
    value: float
    threshold: float
    passed: bool
    description: str


@dataclass
class StatisticalReport:
    n_obs: int
    mean_daily: float
    sd_daily: float
    sharpe_per_period: float
    sharpe_annualized: float
    skew: float
    kurtosis: float
    newey_west_lags: int
    newey_west_t: float
    bootstrap_ci: tuple[float, float]
    bootstrap_confidence: float
    bootstrap_method: str
    bootstrap_block_size: int
    bootstrap_samples: int
    bootstrap_seed: int
    bootstrap_interval_method: str
    n_trials: int
    var_sr: float
    var_sr_source: str
    expected_max_sharpe_per_period: float
    psr_vs_zero: float
    deflated_sharpe: float
    ic_mean: float | None
    ic_std: float | None
    ic_ir: float | None
    ic_t: float | None
    n_ic: int
    turnover_mean: float
    cost_drag_annualized: float
    delay_sharpe_annualized: float | None
    delay_decay: float | None
    min_track_record_length: float | None = None
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_document(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["bootstrap_ci"] = list(self.bootstrap_ci)
        doc["passed"] = self.passed
        doc["format"] = "rsf-statistics/1"
        return doc


def statistical_review(
    net: FloatArray,
    gross: FloatArray,
    *,
    hold_days: int,
    ic_values: list[float],
    turnover: list[float],
    trial_sharpes: list[float],
    n_trials: int,
    thresholds: StatisticalThresholds,
    delay_net: FloatArray | None = None,
) -> StatisticalReport:
    n = len(net)
    sr = sharpe(net) if n else 0.0
    skew, kurt = moments(net) if n > 2 else (0.0, 3.0)
    lags = max(newey_west_lags(n), hold_days) if n else 0
    nw = newey_west_t(net, lags) if n else 0.0
    ci = block_bootstrap_sharpe_ci(
        net, hold_days, thresholds.bootstrap_samples, thresholds.bootstrap_confidence
    )

    # Variance of Sharpe estimates across trials: use the ledger if it has enough results,
    # otherwise the asymptotic variance of a Sharpe estimate under the null, (1 + SR^2/2) / T.
    # Floor: near-duplicate trials must not shrink V[SR] towards zero and switch deflation off.
    null_var = null_sharpe_variance(sr, n)
    if len(trial_sharpes) >= 5:
        ledger_var = float(np.var(trial_sharpes, ddof=1))
        var_sr = max(ledger_var, null_var)
        source = (
            f"ledger ({len(trial_sharpes)} recorded trials)"
            if ledger_var >= null_var
            else f"asymptotic null variance (floor; the ledger's {len(trial_sharpes)} trials vary less than sampling noise)"
        )
    else:
        var_sr = null_var
        source = "asymptotic null variance (fewer than 5 recorded trials)"
    trials = max(1, n_trials)
    sr0 = expected_max_sharpe(trials, var_sr)
    psr0 = probabilistic_sharpe(sr, 0.0, n, skew, kurt)
    dsr = probabilistic_sharpe(sr, sr0, n, skew, kurt)

    ic = np.array(ic_values, dtype=np.float64)
    ic_mean = float(ic.mean()) if len(ic) else None
    ic_std = float(ic.std(ddof=1)) if len(ic) > 1 else None
    ic_ir = ic_mean / ic_std if ic_mean is not None and ic_std else None
    ic_t = ic_ir * math.sqrt(len(ic)) if ic_ir is not None else None

    cost_drag = float((gross - net).mean()) * PERIODS_PER_YEAR if n else 0.0
    delay_sr = (
        sharpe(delay_net) * math.sqrt(PERIODS_PER_YEAR) if delay_net is not None and len(delay_net) else None
    )
    sr_ann = sr * math.sqrt(PERIODS_PER_YEAR)
    decay = (1 - delay_sr / sr_ann) if delay_sr is not None and sr_ann > 0 else None

    th = thresholds
    checks = [
        Check(
            "min_observations", n, th.min_observations, n >= th.min_observations, "enough daily observations"
        ),
        Check(
            "newey_west_t",
            nw,
            th.min_newey_west_t,
            nw >= th.min_newey_west_t,
            "HAC t-statistic of mean return",
        ),
        Check(
            "deflated_sharpe",
            dsr,
            th.min_deflated_sharpe,
            dsr >= th.min_deflated_sharpe,
            f"probability the Sharpe beats the best of {trials} null trials",
        ),
    ]
    if th.require_ci_lower_above_zero:
        checks.append(
            Check("bootstrap_ci_lower", ci[0], 0.0, ci[0] > 0, "bootstrap CI of Sharpe excludes zero")
        )
    if decay is not None:
        checks.append(
            Check(
                "delay_decay",
                decay,
                th.max_delay_sharpe_decay,
                decay <= th.max_delay_sharpe_decay,
                "Sharpe lost with one extra session of execution delay",
            )
        )

    return StatisticalReport(
        n_obs=n,
        mean_daily=float(net.mean()) if n else 0.0,
        sd_daily=float(net.std()) if n else 0.0,
        sharpe_per_period=sr,
        sharpe_annualized=sr_ann,
        skew=skew,
        kurtosis=kurt,
        newey_west_lags=lags,
        newey_west_t=nw,
        bootstrap_ci=ci,
        bootstrap_confidence=th.bootstrap_confidence,
        bootstrap_method="circular_block",
        bootstrap_block_size=max(1, min(hold_days, n)),
        bootstrap_samples=th.bootstrap_samples if n >= 2 else 0,
        bootstrap_seed=BOOTSTRAP_SEED,
        bootstrap_interval_method="percentile",
        n_trials=trials,
        var_sr=var_sr,
        var_sr_source=source,
        expected_max_sharpe_per_period=sr0,
        psr_vs_zero=psr0,
        deflated_sharpe=dsr,
        ic_mean=ic_mean,
        ic_std=ic_std,
        ic_ir=ic_ir,
        ic_t=ic_t,
        n_ic=len(ic),
        turnover_mean=float(np.mean(turnover)) if turnover else 0.0,
        cost_drag_annualized=cost_drag,
        delay_sharpe_annualized=delay_sr,
        delay_decay=decay,
        min_track_record_length=min_track_record_length(sr, skew, kurt, thresholds.bootstrap_confidence),
        checks=checks,
    )
