"""Deterministic long-short backtest (RSF-018).

Conventions (documented, tested):

* At each decision session ``t`` the eligible universe is ranked on ``expected_sign * feature``.
  The top ``quantile`` is held long and the bottom ``quantile`` short, equally weighted,
  0.5 gross each side (dollar-neutral, gross exposure 1).
* Trades execute at the close of session ``t + lag``, where ``lag`` comes from the
  execution delay (see ``calendar.execution_lag_sessions``). Positions earn returns from
  the following session until the next rebalance executes.
* Weights are held constant between rebalances (no drift). Turnover is
  ``sum |w_new - w_old|`` and costs ``turnover * bps / 10_000`` are charged on the
  execution session.
* Returns are split-adjusted. A delisting return is realized on the last listed session;
  afterwards the position earns nothing (cash) until the next rebalance.

Simplifications, deliberately conservative or neutral (audit Q11):

* Constant weights imply small daily rebalancing trades whose costs are not charged.
* Removing a delisted name at the next rebalance is charged as turnover, although no trade
  is possible after delisting.
* No cost is charged for unwinding the final positions at the end of the sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from ..data.calendar import execution_lag_sessions
from ..data.world import MarketDataset
from ..domain.project_models import BacktestSpec
from .features import FeatureTable

FloatArray = npt.NDArray[np.float64]


@dataclass
class BacktestResult:
    sessions: list[int]  # sessions with P&L
    gross: FloatArray
    net: FloatArray
    turnover: list[dict[str, Any]]
    positions: list[dict[str, Any]]
    lag_sessions: int
    execution_delay_minutes: int
    transaction_cost_bps: float
    quantile: float
    universe_by_decision: list[dict[str, Any]]
    ic_by_decision: list[dict[str, Any]]

    def to_document(self, dataset: MarketDataset) -> dict[str, Any]:
        return {
            "format": "rsf-backtest/1",
            "lag_sessions": self.lag_sessions,
            "execution_delay_minutes": self.execution_delay_minutes,
            "transaction_cost_bps": self.transaction_cost_bps,
            "quantile": self.quantile,
            "sessions": [dataset.day(t).isoformat() for t in self.sessions],
            "gross": [float(x) for x in self.gross],
            "net": [float(x) for x in self.net],
            "turnover": self.turnover,
            "positions": self.positions,
            "universe_by_decision": self.universe_by_decision,
            "ic_by_decision": self.ic_by_decision,
        }


def _rank(values: FloatArray) -> FloatArray:
    """Average ranks (ties share the mean rank), 1-based."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values))
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def spearman(a: FloatArray, b: FloatArray) -> float | None:
    if len(a) < 3:
        return None
    ra, rb = _rank(a), _rank(b)
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return None
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (sa * sb))


def run_backtest(
    dataset: MarketDataset,
    table: FeatureTable,
    spec: BacktestSpec,
    expected_sign: int = 1,
    extra_lag_sessions: int = 0,
) -> BacktestResult:
    returns = dataset.adjusted_returns
    t_count, n = returns.shape
    held_returns = np.nan_to_num(returns, nan=0.0)
    lag = execution_lag_sessions(spec.execution_delay_minutes) + extra_lag_sessions
    end_idx = int(np.searchsorted(dataset.trading_days, np.datetime64(spec.end, "D"), side="right")) - 1

    weights = np.zeros((t_count, n))
    cost = np.zeros(t_count)
    turnover_log: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    universe_log: list[dict[str, Any]] = []
    ic_log: list[dict[str, Any]] = []
    previous = np.zeros(n)
    executions: list[tuple[int, FloatArray]] = []

    for r, t in enumerate(table.sessions):
        execute = t + lag
        if execute >= end_idx:
            break
        eligible = table.universe[r] & np.isfinite(table.values[r])
        universe_log.append(
            {
                "decision": dataset.day(t).isoformat(),
                "universe": [dataset.security_ids[i] for i in np.flatnonzero(table.universe[r])],
            }
        )
        target = np.zeros(n)
        idx = np.flatnonzero(eligible)
        k = int(np.floor(len(idx) * spec.quantile))
        if k >= 1:
            scores = expected_sign * table.values[r, idx]
            order = idx[np.argsort(scores, kind="mergesort")]  # stable: ties keep security order
            shorts, longs = order[:k], order[-k:]
            target[longs] = 0.5 / k
            target[shorts] = -0.5 / k
            positions.append(
                {
                    "decision": dataset.day(t).isoformat(),
                    "execution": dataset.day(execute).isoformat(),
                    "long": sorted(dataset.security_ids[i] for i in longs),
                    "short": sorted(dataset.security_ids[i] for i in shorts),
                }
            )
            # Information coefficient: score vs. forward return over the holding window.
            hold_end = min(execute + spec.hold_days, end_idx)
            fwd = np.prod(1.0 + held_returns[execute + 1 : hold_end + 1][:, idx], axis=0) - 1.0
            ic = spearman(scores, fwd)
            if ic is not None:
                ic_log.append({"decision": dataset.day(t).isoformat(), "ic": ic, "n": len(idx)})
        traded = float(np.abs(target - previous).sum())
        cost[execute] += traded * spec.transaction_cost_bps / 10_000.0
        turnover_log.append(
            {
                "execution": dataset.day(execute).isoformat(),
                "turnover": traded,
                "cost": traded * spec.transaction_cost_bps / 10_000.0,
            }
        )
        executions.append((execute, target))
        previous = target

    for j, (execute, target) in enumerate(executions):
        stop = executions[j + 1][0] if j + 1 < len(executions) else end_idx
        weights[execute + 1 : stop + 1] = target

    if not executions:
        sessions: list[int] = []
        gross = np.zeros(0)
        net = np.zeros(0)
    else:
        first = executions[0][0]
        sessions = list(range(first, end_idx + 1))
        daily = (weights * held_returns).sum(axis=1)
        gross = daily[first : end_idx + 1]
        net = gross - cost[first : end_idx + 1]

    return BacktestResult(
        sessions=sessions,
        gross=gross,
        net=net,
        turnover=turnover_log,
        positions=positions,
        lag_sessions=lag,
        execution_delay_minutes=spec.execution_delay_minutes,
        transaction_cost_bps=spec.transaction_cost_bps,
        quantile=spec.quantile,
        universe_by_decision=universe_log,
        ic_by_decision=ic_log,
    )
