"""Real SEC EDGAR filings with semi-synthetic prices (RSF-057, ADR-0003).

Filings, acceptance times, restatements and listing windows are real (public-domain SEC
data, recorded in ``snapshots/edgar_universe_v1.json.gz``). Prices are simulated for those
companies by ``price_sim``, with a planted relationship to the EPS feature keyed to the
*real* acceptance times. A period-end leak therefore inflates results by a known amount on
real filing-timing quirks. Prices are always labelled as simulated.
"""

from __future__ import annotations

from pathlib import Path

from .calendar import close_epochs, trading_days
from .edgar_universe import WINDOW_END, WINDOW_START, read_snapshot, securities_and_filings
from .price_sim import PriceSimParams, simulate_prices
from .world import MarketDataset

SNAPSHOT = Path(__file__).parent / "snapshots" / "edgar_universe_v1.json.gz"
SEED = 2026


def load_edgar_semi_synthetic(path: Path = SNAPSHOT, params: PriceSimParams | None = None) -> MarketDataset:
    doc = read_snapshot(path)
    securities, filings = securities_and_filings(doc)
    days = trading_days(WINDOW_START, WINDOW_END)
    prices = simulate_prices(days, close_epochs(days), securities, filings, params or PriceSimParams(seed=SEED, n_splits=0))
    return MarketDataset(
        dataset_id="edgar-semi:v1",
        description="Real SEC EDGAR filings (44 companies, 2019-2023) with simulated prices",
        trading_days=days,
        security_ids=tuple(s.security_id for s in securities),
        raw_close=prices.raw_close,
        split_ratio=prices.split_ratio,
        securities=securities,
        filings=filings,
        prices_simulated=True,
        planted={
            **prices.planted,
            "world": "edgar-semi/1",
            "snapshot_built_at": doc["built_at"],
            "snapshot_source": doc["source"],
            "provenance_count": len(doc["provenance"]),
            "delisted": [s.security_id for s in securities if s.listed_to is not None],
            "ipos": [s.security_id for s in securities if s.listed_from > WINDOW_START],
            "restatement_accessions": [f.accession for f in filings if f.amends],
        },
    )
