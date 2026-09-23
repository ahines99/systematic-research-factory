"""Price simulation with a planted, acceptance-timed earnings signal of known strength.

Used for both the fully synthetic fixture and the semi-synthetic EDGAR universe (ADR-0003).
The market reacts to each original filing only once it has been *accepted* by the SEC:

* on the first session whose close is at or after acceptance, the stock jumps by
  ``jump_beta * z``;
* over the next ``drift_days`` sessions it drifts by a further ``drift_gamma * z`` in total,

where ``z`` is the clipped, standardized year-over-year EPS change known at acceptance.
An honest strategy (acceptance timing, positive execution delay) can only capture the
drift. A strategy that uses period-end timing also captures the jump, which inflates its
results by a known amount. That is the ground truth the leakage audit is scored against.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .calendar import first_close_at_or_after
from .fundamentals import FilingIndex, yoy_change
from .world import Filing, FloatArray, Security


@dataclass(frozen=True)
class PriceSimParams:
    seed: int = 7
    jump_beta: float = 0.04
    drift_gamma: float = 0.03
    drift_days: int = 20
    market_mu: float = 0.0003
    market_sigma: float = 0.010
    idio_sigma_low: float = 0.015
    idio_sigma_high: float = 0.025
    default_delisting_return: float = -0.30
    n_splits: int = 3
    feature_clip: float = 3.0


@dataclass(frozen=True)
class SimulatedPrices:
    raw_close: FloatArray
    split_ratio: FloatArray
    planted: dict[str, Any]


def simulate_prices(
    trading_days: np.ndarray,
    closes: np.ndarray,
    securities: Sequence[Security],
    filings: Sequence[Filing],
    params: PriceSimParams,
) -> SimulatedPrices:
    rng = np.random.default_rng(params.seed)
    t_count, n_count = len(trading_days), len(securities)
    days = [d.item() for d in trading_days]
    index = {s.security_id: i for i, s in enumerate(securities)}

    betas = rng.uniform(0.7, 1.3, n_count)
    sigmas = rng.uniform(params.idio_sigma_low, params.idio_sigma_high, n_count)
    market = rng.normal(params.market_mu, params.market_sigma, t_count)
    returns = betas[None, :] * market[:, None] + rng.normal(0.0, 1.0, (t_count, n_count)) * sigmas[None, :]

    # --- planted acceptance-timed signal -------------------------------------------
    fidx = FilingIndex(filings)
    events: list[tuple[int, int, float]] = []
    for f in filings:
        if f.is_amendment or f.security_id not in index:
            continue
        prior = fidx.version_known_at(f.security_id, FilingIndex.year_ago(f.fiscal_period), f.accepted_at)
        if prior is None:
            continue
        a = first_close_at_or_after(closes, f.accepted_at)
        if a <= 0 or a >= t_count:
            continue
        events.append((index[f.security_id], a, yoy_change(f.eps, prior.eps)))

    xs = np.array([e[2] for e in events], dtype=np.float64)
    mean = float(xs.mean()) if len(xs) else 0.0
    std = float(xs.std()) if len(xs) > 1 else 1.0
    std = std if std > 0 else 1.0
    zs = np.clip((xs - mean) / std, -params.feature_clip, params.feature_clip)
    h = params.drift_days
    for (i, a, _), z in zip(events, zs, strict=True):
        returns[a, i] += params.jump_beta * z
        returns[a + 1 : a + 1 + h, i] += params.drift_gamma * z / h

    # --- listing, delisting, splits -------------------------------------------------
    listed = np.array([[s.is_listed(d) for s in securities] for d in days], dtype=bool)
    delisting_returns: dict[str, float] = {}
    for i, s in enumerate(securities):
        if s.listed_to is None:
            continue
        last = [t for t in range(t_count) if listed[t, i]]
        if not last:
            continue
        dr = s.delisting_return if s.delisting_return is not None else params.default_delisting_return
        returns[last[-1], i] = (1.0 + returns[last[-1], i]) * (1.0 + dr) - 1.0
        delisting_returns[s.security_id] = dr

    split_ratio = np.ones((t_count, n_count))
    long_lived = [i for i in range(n_count) if listed[:, i].sum() > 500]
    split_ids: list[dict[str, Any]] = []
    if long_lived and params.n_splits:
        chosen = rng.choice(long_lived, size=min(params.n_splits, len(long_lived)), replace=False)
        for i in sorted(int(c) for c in chosen):
            live = np.flatnonzero(listed[:, i])
            t = int(live[len(live) // 2])
            split_ratio[t, i] = 2.0
            split_ids.append(
                {"security_id": securities[i].security_id, "session": str(trading_days[t]), "ratio": 2.0}
            )

    start_prices = rng.uniform(20.0, 120.0, n_count)
    raw_close = np.full((t_count, n_count), np.nan)
    for i in range(n_count):
        prev = math.nan
        for t in range(t_count):
            if not listed[t, i]:
                prev = math.nan
                continue
            if math.isnan(prev):
                raw_close[t, i] = start_prices[i]
            else:
                raw_close[t, i] = prev * (1.0 + returns[t, i]) / split_ratio[t, i]
            prev = raw_close[t, i]
    raw_close = np.round(raw_close, 6)

    var_z = float(zs.var()) if len(zs) else 0.0
    noise_var = h * float(np.mean(sigmas**2 + (betas * params.market_sigma) ** 2))
    denom = math.sqrt(params.drift_gamma**2 * var_z + noise_var) if var_z + noise_var > 0 else 1.0
    expected_event_ic = params.drift_gamma * math.sqrt(var_z) / denom if denom else 0.0

    planted = {
        "generator": "price_sim/1",
        "params": asdict(params),
        "feature": "eps_yoy_change",
        "knowledge_basis": "acceptance",
        "feature_mean": mean,
        "feature_std": std,
        "n_events": len(events),
        "expected_event_ic": expected_event_ic,
        "event_ic_definition": (
            "Pearson correlation between the standardized feature z at acceptance and the "
            f"{h}-session forward return starting the session after the announcement close"
        ),
        "splits": split_ids,
        "delisting_returns": delisting_returns,
    }
    return SimulatedPrices(raw_close=raw_close, split_ratio=split_ratio, planted=planted)
