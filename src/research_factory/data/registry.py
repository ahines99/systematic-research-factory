"""Named datasets. A hypothesis refers to one by name in ``universe.dataset``."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache

from ..domain.errors import NotFoundError
from .price_sim import PriceSimParams
from .synthetic import generate_synthetic_world
from .world import MarketDataset


def _synthetic(name: str, **sim: float) -> Callable[[], MarketDataset]:
    def build() -> MarketDataset:
        return generate_synthetic_world(seed=7, sim=PriceSimParams(seed=7, **sim), dataset_id=name)  # type: ignore[arg-type]

    return build


def _edgar_semi() -> MarketDataset:
    from .semi_synthetic import load_edgar_semi_synthetic

    return load_edgar_semi_synthetic()


BUILDERS: dict[str, Callable[[], MarketDataset]] = {
    # Planted acceptance-timed signal of known strength.
    "synthetic:v1": _synthetic("synthetic:v1"),
    # No signal at all: every apparent edge is noise.
    "synthetic:v1:null": _synthetic("synthetic:v1:null", jump_beta=0.0, drift_gamma=0.0),
    # A weak signal: significant on its own, not after honest multiple-testing correction.
    "synthetic:v1:weak": _synthetic("synthetic:v1:weak", jump_beta=0.02, drift_gamma=0.018),
    # Real SEC EDGAR filings with semi-synthetic prices (ADR-0003).
    "edgar-semi:v1": _edgar_semi,
}


@cache
def get_dataset(name: str) -> MarketDataset:
    try:
        builder = BUILDERS[name]
    except KeyError as exc:
        raise NotFoundError(f"unknown dataset {name!r}; known: {sorted(BUILDERS)}") from exc
    return builder()


def dataset_names() -> list[str]:
    return sorted(BUILDERS)
