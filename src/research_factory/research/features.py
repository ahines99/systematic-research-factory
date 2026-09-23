"""Feature build with knowledge-time lineage (RSF-017).

Every feature value records the evidence it was built from and the time each input
became knowable. The leakage audit re-derives those times from the evidence itself rather
than trusting what the builder claims.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np
import numpy.typing as npt

from ..data.calendar import close_utc
from ..data.fundamentals import FilingIndex, yoy_change
from ..data.world import MarketDataset
from ..domain.errors import InvalidInputError
from ..domain.project_models import TimingBasis, UniverseMode

STALE_AFTER_DAYS = 200


@dataclass(frozen=True, slots=True)
class LineageInput:
    evidence_id: str
    locator: str  # "filing:<accession>" or "price:<security_id>:<YYYY-MM-DD>"
    knowledge_ts: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "locator": self.locator,
            "knowledge_ts": self.knowledge_ts.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class FeatureValue:
    value: float
    inputs: tuple[LineageInput, ...]


@dataclass
class FeatureContext:
    dataset: MarketDataset
    filings: FilingIndex
    timing_basis: TimingBasis
    filings_evidence_id: str
    prices_evidence_id: str

    def close(self, t: int) -> datetime:
        return close_utc(self.dataset.day(t))


ComputeFn = Callable[[FeatureContext, str, int], FeatureValue | None]


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    description: str
    input_sources: frozenset[str]  # "filing", "price", "forward_return"
    compute: ComputeFn
    timing_sensitive: bool = False  # whether timing_basis applies


# --------------------------------------------------------------------------- features


def _filing_input(ctx: FeatureContext, accession: str) -> LineageInput:
    f = ctx.filings.by_accession[accession]
    return LineageInput(ctx.filings_evidence_id, f"filing:{accession}", f.accepted_at)


def eps_yoy_change(ctx: FeatureContext, sid: str, t: int) -> FeatureValue | None:
    """Year-over-year change in quarterly EPS, scaled by the prior-year level."""
    decision_ts = ctx.close(t)
    day = ctx.dataset.day(t)
    idx = ctx.filings
    basis = ctx.timing_basis
    if basis is TimingBasis.ACCEPTANCE:
        latest = idx.latest_original_known_at(sid, decision_ts)
        if latest is None:
            return None
        current = idx.version_known_at(sid, latest.fiscal_period, decision_ts)
        prior = idx.version_known_at(sid, FilingIndex.year_ago(latest.fiscal_period), decision_ts)
    elif basis is TimingBasis.PERIOD_END:
        current = idx.latest_original_by_period_end(sid, day)
        prior = idx.original(sid, FilingIndex.year_ago(current.fiscal_period)) if current else None
    else:  # LATEST_RESTATED
        latest = idx.latest_original_known_at(sid, decision_ts)
        if latest is None:
            return None
        current = idx.final_version(sid, latest.fiscal_period)
        prior = idx.final_version(sid, FilingIndex.year_ago(latest.fiscal_period))
    if current is None or prior is None:
        return None
    if (day - current.period_end).days > STALE_AFTER_DAYS:
        return None
    return FeatureValue(
        yoy_change(current.eps, prior.eps),
        (_filing_input(ctx, current.accession), _filing_input(ctx, prior.accession)),
    )


def _price_input(ctx: FeatureContext, sid: str, t: int) -> LineageInput:
    return LineageInput(ctx.prices_evidence_id, f"price:{sid}:{ctx.dataset.day(t).isoformat()}", ctx.close(t))


def momentum_60_5(ctx: FeatureContext, sid: str, t: int) -> FeatureValue | None:
    """Cumulative return from 60 to 5 sessions ago (skipping the most recent week)."""
    if t < 60:
        return None
    i = ctx.dataset.index[sid]
    window = ctx.dataset.adjusted_returns[t - 59 : t - 4, i]
    if np.isnan(window).any():
        return None
    return FeatureValue(
        float(np.prod(1.0 + window) - 1.0), (_price_input(ctx, sid, t - 60), _price_input(ctx, sid, t - 5))
    )


def forward_return_20d(ctx: FeatureContext, sid: str, t: int) -> FeatureValue | None:
    """The next 20 sessions' return. This is the *target*; using it as a feature is leakage."""
    T = len(ctx.dataset.trading_days)
    if t + 20 >= T:
        return None
    i = ctx.dataset.index[sid]
    window = ctx.dataset.adjusted_returns[t + 1 : t + 21, i]
    if np.isnan(window).any():
        return None
    return FeatureValue(float(np.prod(1.0 + window) - 1.0), (_price_input(ctx, sid, t + 20),))


FEATURES: dict[str, FeatureDefinition] = {
    "eps_yoy_change": FeatureDefinition(
        "eps_yoy_change",
        "Year-over-year change in quarterly EPS, scaled by |prior-year EPS| (floor 0.25)",
        frozenset({"filing"}),
        eps_yoy_change,
        timing_sensitive=True,
    ),
    "momentum_60_5": FeatureDefinition(
        "momentum_60_5", "Return from t-60 to t-5 sessions", frozenset({"price"}), momentum_60_5
    ),
    "forward_return_20d": FeatureDefinition(
        "forward_return_20d",
        "Return over the next 20 sessions (the prediction target; never a valid feature)",
        frozenset({"forward_return"}),
        forward_return_20d,
    ),
}


def get_feature(name: str) -> FeatureDefinition:
    try:
        return FEATURES[name]
    except KeyError as exc:
        raise InvalidInputError(f"unknown feature {name!r}; known: {sorted(FEATURES)}") from exc


# --------------------------------------------------------------------------- build


@dataclass
class FeatureTable:
    feature: str
    timing_basis: TimingBasis
    universe_mode: UniverseMode
    sessions: list[int]  # rebalance (decision) session indices
    security_ids: tuple[str, ...]
    values: npt.NDArray[np.float64]  # [R, N], NaN where unavailable
    universe: npt.NDArray[np.bool_]  # [R, N], eligible securities at each decision
    lineage: list[dict[str, Any]] = field(default_factory=list)

    def to_document(self, dataset: MarketDataset) -> dict[str, Any]:
        return {
            "format": "rsf-feature-table/1",
            "feature": self.feature,
            "timing_basis": str(self.timing_basis),
            "universe_mode": str(self.universe_mode),
            "security_ids": list(self.security_ids),
            "sessions": [dataset.day(t).isoformat() for t in self.sessions],
            "values": [[None if np.isnan(v) else float(v) for v in row] for row in self.values],
            "universe": [
                [sid for sid, ok in zip(self.security_ids, row, strict=True) if ok] for row in self.universe
            ],
            "lineage": {"feature": self.feature, "rows": self.lineage},
        }

    @classmethod
    def from_document(cls, doc: dict[str, Any], dataset: MarketDataset) -> FeatureTable:
        ids = tuple(doc["security_ids"])
        sessions = [dataset.session_index(date.fromisoformat(d)) for d in doc["sessions"]]
        values = np.array(
            [[np.nan if v is None else v for v in row] for row in doc["values"]], dtype=np.float64
        )
        universe = np.array([[sid in set(row) for sid in ids] for row in doc["universe"]], dtype=bool)
        return cls(
            feature=doc["feature"],
            timing_basis=TimingBasis(doc["timing_basis"]),
            universe_mode=UniverseMode(doc["universe_mode"]),
            sessions=sessions,
            security_ids=ids,
            values=values.reshape(len(sessions), len(ids)),
            universe=universe.reshape(len(sessions), len(ids)),
            lineage=doc["lineage"]["rows"],
        )


def rebalance_sessions(dataset: MarketDataset, start: Any, end: Any, hold_days: int) -> list[int]:
    days = dataset.trading_days
    first = int(np.searchsorted(days, np.datetime64(start, "D")))
    last = int(np.searchsorted(days, np.datetime64(end, "D"), side="right")) - 1
    return list(range(first, last + 1, hold_days))


def build_features(
    dataset: MarketDataset,
    *,
    feature: str,
    timing_basis: TimingBasis,
    universe_mode: UniverseMode,
    sessions: list[int],
    filings_evidence_id: str,
    prices_evidence_id: str,
) -> FeatureTable:
    definition = get_feature(feature)
    ctx = FeatureContext(
        dataset, FilingIndex(dataset.filings), timing_basis, filings_evidence_id, prices_evidence_id
    )
    n = len(dataset.security_ids)
    values = np.full((len(sessions), n), np.nan)
    listed = dataset.listed_mask
    if universe_mode is UniverseMode.CURRENT_CONSTITUENTS:
        survivors = listed[-1]
    universe = np.zeros((len(sessions), n), dtype=bool)
    lineage: list[dict[str, Any]] = []
    for r, t in enumerate(sessions):
        eligible = listed[t] & survivors if universe_mode is UniverseMode.CURRENT_CONSTITUENTS else listed[t]
        universe[r] = eligible
        decision = close_utc(dataset.day(t)).isoformat()
        for i in np.flatnonzero(eligible):
            sid = dataset.security_ids[i]
            fv = definition.compute(ctx, sid, t)
            if fv is None:
                continue
            values[r, i] = fv.value
            lineage.append(
                {
                    "security_id": sid,
                    "decision_ts": decision,
                    "value": fv.value,
                    "inputs": [inp.to_dict() for inp in fv.inputs],
                }
            )
    return FeatureTable(
        feature, timing_basis, universe_mode, sessions, dataset.security_ids, values, universe, lineage
    )
