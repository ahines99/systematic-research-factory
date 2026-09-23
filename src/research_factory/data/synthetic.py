"""Deterministic synthetic research world (RSF-008, RSF-009).

The same seed always produces byte-identical output. Planted effects, recorded in
``dataset.planted``:

* an acceptance-timed earnings signal of known strength (see ``price_sim``);
* delisted securities (survivorship trap) with a final delisting return;
* IPOs part-way through the sample;
* a ticker reused by a different company after the first one delists;
* 2-for-1 splits (raw prices halve, adjusted returns do not);
* filings accepted after the 16:00 close (tradable only at the next close);
* restatements: amended filings accepted months later with different EPS
  (``latest_restated`` timing back-fills them: a look-ahead leak);
* period-end timing is a look-ahead leak of roughly 30-75 days.
"""

from __future__ import annotations

import string
from datetime import UTC, date, datetime, time, timedelta

import numpy as np

from .calendar import EASTERN, close_epochs, trading_days
from .price_sim import PriceSimParams, simulate_prices
from .world import Filing, MarketDataset, Security, TickerInterval

FIRST_FISCAL_YEAR = 2017


def _quarter_end(year: int, q: int) -> date:
    month = q * 3
    next_month = date(year + (month // 12), month % 12 + 1, 1)
    return next_month - timedelta(days=1)


def _next_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _random_day(rng: np.random.Generator, lo: date, hi: date) -> date:
    return _next_weekday(lo + timedelta(days=int(rng.integers(0, (hi - lo).days + 1))))


def _accepted_at(rng: np.random.Generator, filed: date, after_close_prob: float = 0.3) -> datetime:
    if rng.random() < after_close_prob:
        minutes = int(rng.integers(16 * 60 + 5, 21 * 60 + 30))
    else:
        minutes = int(rng.integers(6 * 60, 15 * 60 + 55))
    local = datetime.combine(filed, time(minutes // 60, minutes % 60), tzinfo=EASTERN)
    return local.astimezone(UTC)


def _tickers(rng: np.random.Generator, n: int) -> list[str]:
    letters = np.array(list(string.ascii_uppercase))
    seen: set[str] = set()
    out: list[str] = []
    while len(out) < n:
        t = "".join(rng.choice(letters, size=4))
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def generate_synthetic_world(
    seed: int = 7,
    n_securities: int = 50,
    start: date = date(2019, 1, 2),
    end: date = date(2023, 12, 29),
    n_delist: int = 6,
    n_ipo: int = 5,
    n_restatements: int = 10,
    sim: PriceSimParams | None = None,
    dataset_id: str | None = None,
) -> MarketDataset:
    rng = np.random.default_rng(seed)
    days = trading_days(start, end)
    tickers = _tickers(rng, n_securities)

    order = rng.permutation(n_securities)
    delisters = sorted(int(i) for i in order[:n_delist])
    ipos = sorted(int(i) for i in order[n_delist : n_delist + n_ipo])

    listed_from = {i: start for i in range(n_securities)}
    listed_to: dict[int, date | None] = {i: None for i in range(n_securities)}
    for i in delisters:
        listed_to[i] = _random_day(rng, date(2020, 3, 2), date(2023, 6, 30))
    for i in ipos:
        listed_from[i] = _random_day(rng, date(2020, 6, 1), date(2022, 6, 30))

    # Ticker reuse: the earliest delister's ticker passes to an IPO listed after it.
    reuse: dict[str, str] = {}
    ticker_of = {i: tickers[i] for i in range(n_securities)}
    if delisters and ipos:
        src = min(delisters, key=lambda i: listed_to[i] or end)
        dst = ipos[0]
        src_end = listed_to[src]
        assert src_end is not None
        if listed_from[dst] <= src_end + timedelta(days=30):
            listed_from[dst] = _next_weekday(min(src_end + timedelta(days=60), end - timedelta(days=400)))
        ticker_of[dst] = tickers[src]
        reuse = {
            "ticker": tickers[src],
            "first_security": f"SYN{src:03d}",
            "second_security": f"SYN{dst:03d}",
        }

    securities = tuple(
        Security(
            security_id=f"SYN{i:03d}",
            name=f"Synthetic Company {i:03d}",
            listed_from=listed_from[i],
            listed_to=listed_to[i],
            tickers=(TickerInterval(ticker_of[i], listed_from[i], listed_to[i]),),
        )
        for i in range(n_securities)
    )

    # --- filings ------------------------------------------------------------------
    filings: list[Filing] = []
    for i, sec in enumerate(securities):
        level = rng.uniform(0.5, 3.0)
        growth = rng.normal(0.06, 0.08)
        seasonal = rng.normal(0.0, 0.05 * level, 4)
        shock = 0.0
        seq = 0
        q_index = 0
        year = FIRST_FISCAL_YEAR
        while True:
            for q in range(1, 5):
                period_end = _quarter_end(year, q)
                shock = 0.5 * shock + rng.normal(0.0, 0.12 * level)
                eps = round(level * (1 + growth) ** (q_index / 4) + seasonal[q - 1] + shock, 2)
                q_index += 1
                lag = int(rng.integers(55, 76)) if q == 4 else int(rng.integers(30, 46))
                filed = _next_weekday(period_end + timedelta(days=lag))
                accepted = _accepted_at(rng, filed)
                if period_end > end or filed > end:
                    continue
                if filed < sec.listed_from - timedelta(days=450):
                    continue
                if sec.listed_to is not None and filed > sec.listed_to:
                    continue
                seq += 1
                filings.append(
                    Filing(
                        accession=f"{9900000000 + i:010d}-{filed.year % 100:02d}-{seq:06d}",
                        security_id=sec.security_id,
                        form="10-K" if q == 4 else "10-Q",
                        fiscal_period=f"{year}Q{q}",
                        period_end=period_end,
                        filed_date=filed,
                        accepted_at=accepted,
                        eps=eps,
                    )
                )
            year += 1
            if _quarter_end(year, 1) > end:
                break

    # --- restatements -------------------------------------------------------------
    candidates = [f for f in filings if start <= f.period_end <= end - timedelta(days=300)]
    restated: list[str] = []
    picks = rng.choice(len(candidates), size=min(n_restatements, len(candidates)), replace=False)
    sec_by_id = {s.security_id: s for s in securities}
    for p in sorted(int(x) for x in picks):
        original = candidates[p]
        filed = _next_weekday(original.filed_date + timedelta(days=int(rng.integers(60, 201))))
        sec = sec_by_id[original.security_id]
        if filed > end or (sec.listed_to is not None and filed > sec.listed_to):
            continue
        delta = rng.normal(0.0, 0.25 * max(abs(original.eps), 0.5))
        amendment = Filing(
            accession=f"{original.accession[:-6]}{900000 + len(restated):06d}",
            security_id=original.security_id,
            form=f"{original.form}/A",
            fiscal_period=original.fiscal_period,
            period_end=original.period_end,
            filed_date=filed,
            accepted_at=_accepted_at(rng, filed),
            eps=round(original.eps + delta, 2),
            amends=original.accession,
            revision="restated",
        )
        filings.append(amendment)
        restated.append(amendment.accession)

    filings.sort(key=lambda f: (f.accepted_at, f.accession))
    params = sim or PriceSimParams(seed=seed)
    prices = simulate_prices(days, close_epochs(days), securities, filings, params)

    after_close = sum(1 for f in filings if f.accepted_at.astimezone(EASTERN).time() >= time(16, 0))
    planted = {
        **prices.planted,
        "world": "synthetic/1",
        "seed": seed,
        "delisted": [f"SYN{i:03d}" for i in delisters],
        "ipos": [f"SYN{i:03d}" for i in ipos],
        "ticker_reuse": reuse,
        "restatement_accessions": restated,
        "after_close_filings": after_close,
        "leak_variants": {
            "period_end": "feature treated as known at fiscal period end: 30-75 days of look-ahead",
            "latest_restated": "final restated EPS back-filled to the original date",
            "current_constituents": "universe restricted to securities listed at the end of the sample",
        },
    }
    return MarketDataset(
        dataset_id=dataset_id or f"synthetic:v1:seed{seed}",
        description="Fully synthetic world with planted signal, leaks and survivorship traps",
        trading_days=days,
        security_ids=tuple(s.security_id for s in securities),
        raw_close=prices.raw_close,
        split_ratio=prices.split_ratio,
        securities=securities,
        filings=tuple(filings),
        prices_simulated=True,
        planted=planted,
    )
