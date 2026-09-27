# Quantitative, point-in-time and data audit — 2026-09-27

Scope: research modules, data models/adapters/simulation/PIT, experiment contracts, ledger trial policy, associated tests, ADRs 0003/0007/0008. Read-only source audit plus offline Python probes using the existing virtual environment; no SEC calls, production DB writes, paid calls or code modifications. Full workflow probe used SQLite memory and memory blob store. Root agent owns baseline test suite.

## Existing implementation

- Deterministic synthetic worlds with IPOs, delistings, ticker reuse, splits, restatements and acceptance-timed planted effects. Named null/weak/fast signal variants exist.
- Committed SEC-derived snapshot: 44 securities, 1,325 filing/version records, 227 provenance records, built 2026-09-23T18:58:13+00:00. Extraction totals: 1,246 originals, 60 restated, 19 split-adjusted; Q4 96 reported / 143 net-income-derived / 7 EPS-derived / 23 skipped.
- Timezone-aware PIT access; acceptance-keyed filing version lookup; close-bounded price reads; future delisting/ticker hiding; deterministic snapshot serialization.
- Three feature implementations: EPS year-over-year, momentum 60-to-5, deliberately invalid forward return. Every computed value has source lineage. Deliberate period-end/restated/current-constituent leak modes are evaluation fixtures.
- Long/short quantile backtest with explicit close execution lag, transaction costs, turnover, IC, split-adjusted returns, delisting returns and delayed rerun.
- Statistical review: annualized Sharpe, skew/kurtosis, HAC Newey-West t, circular block-bootstrap CI, PSR/DSR, null variance floor, trial count, IC statistics, delay decay and minimum track record length.
- Immutable experiment identity; consistent hold/horizon contract; freeze-time statistical context; related-feature/dataset trial counting across family names at committee time. Existing reference/hand-computation and golden tests cover the major happy paths and earlier audit fixes.

## Confirmed remaining work

### QUANT-1 — High: incomplete requested date ranges can reach an approve recommendation

Locations: `src/research_factory/workflows/steps.py:153` and `:178`; `src/research_factory/research/features.py:215`; `src/research_factory/research/backtest.py:108`.

Data acquisition checks the contents of the available snapshot but does not check that it covers the frozen backtest range. Searchsorted clips end dates beyond the dataset to its last session; start dates before the first session are also silently clipped. This changes the tested hypothesis without requiring a newly frozen experiment.

Observed full supported workflow: a normal synthetic experiment with end `2025-12-31`, as_of `2026-01-01`, default start `2019-06-03` reaches `needs_review` at Research committee with reason **the gate recommends approve**. Data acquisition reports first/last sessions `2019-01-02` / `2023-12-29`; statistical review passes with 1,194 observations. Findings contain no missing-range warning. Direct backtest requested `2010-01-01` to `2025-12-31` returned P&L `2019-01-03` to `2023-12-29`, 1,302 observations.

Acceptance: before computation, compare the frozen requested range against available session coverage and as_of-close availability. Unsupported ranges must fail validation or produce blocking NEEDS_EVIDENCE. Handle weekends according to the documented calendar rather than requiring literal start/end date rows. Test pre-dataset starts, post-dataset ends, an as_of instant before the requested final close, and valid weekend endpoints. Do not silently rewrite the frozen range.

Offline reproduction (execute with `.venv/Scripts/python.exe`):

```python
import asyncio
from datetime import date, datetime, UTC
from tests.conftest import make_experiment
from research_factory.config import Settings
from research_factory.services.container import build_services
from research_factory.workflows.primary import primary_engine
async def probe():
    s = build_services(Settings(database_url="sqlite://", blob_store="memory://",
                                model_provider="rules", _env_file=None))
    e = make_experiment(end=date(2025,12,31), as_of=datetime(2026,1,1,tzinfo=UTC))
    s.ledger.freeze(e, "audit")
    run = await primary_engine(s).start(e.experiment_id, "audit")
    print(run.status, run.status_reason)
    for name in ["Data acquisition", "Statistical review"]:
        result = s.repos.steps.get(run.run_id, name)
        doc = s.evidence.load_json(result.artifact_evidence_id)
        print(name, {k: doc[k] for k in ["first_session", "last_session", "passed", "n_obs"] if k in doc})
asyncio.run(probe())
```

### QUANT-2 — Medium: NaN recomputation fails open in the supposedly independent lineage audit

Locations: `src/research_factory/research/leakage.py:206`, `:259`, especially `:262`; related decision/source validation at `:80` and `:219`. Contradicts the builder-independent verification claim in `docs/architecture.md:112`.

For momentum, a cited window containing pre-IPO missing returns recomputes to NaN. `abs(expected - value) > tolerance` evaluates false for NaN, so a fabricated finite value passes. I changed one post-IPO momentum value and matching lineage value to `123456789.0`, cited session 0 and 1 (before that security listed), and set their true close times. Recomputed value was `nan`; **all six leakage checks passed**, zero violations.

Reachability: this is a direct audit-function / corrupted-or-faulty feature-builder boundary weakness. Current MCP analysis tools compute built-in features internally; they do not accept caller-supplied feature tables. The honest momentum builder rejects missing windows. Therefore this is not demonstrated as an unauthenticated remote approval exploit. It does undermine the explicit independent-auditor guarantee and the existing tests that intentionally simulate a dishonest builder.

Acceptance: require finite claimed and recomputed values; reject non-finite or absent source observations; bind locator security, exact feature window and filing identity/period semantics to the row. Independently derive decision close from the session rather than accepting any time on the same Eastern date. Add adversarial tests for a pre-IPO price window, altered source security, reversed window, duplicate/orphan lineage and a same-date altered decision timestamp. Keep ordinary valid feature checks passing.

Compact reproduction using test fixture helpers:

```python
from copy import deepcopy
from datetime import datetime, UTC
from research_factory.data.registry import get_dataset
from research_factory.data.pit import PointInTimeData
from research_factory.data.calendar import EASTERN, close_utc
from research_factory.data.world import filing_to_dict
from research_factory.research.backtest import run_backtest
from research_factory.research.leakage import audit_leakage, recompute
from tests.test_research import _table
from tests.conftest import make_experiment
v = PointInTimeData(get_dataset("synthetic:v1")).view_as_of(datetime(2023,12,30,tzinfo=UTC))
t = _table(v, feature="momentum_60_5")
d = deepcopy(t.to_document(v))
ipo = next(s for s in v.securities if s.listed_from > v.day(3))
r = next(r for r in d["lineage"]["rows"] if r["security_id"] == ipo.security_id)
r["value"] = 123456789.0
for inp, idx in zip(r["inputs"], [0, 1]):
    inp["locator"] = f"price:{ipo.security_id}:{v.day(idx)}"
    inp["knowledge_ts"] = close_utc(v.day(idx)).isoformat()
ri = d["sessions"].index(datetime.fromisoformat(r["decision_ts"]).astimezone(EASTERN).date().isoformat())
d["values"][ri][d["security_ids"].index(ipo.security_id)] = r["value"]
b = run_backtest(v,t,make_experiment(feature="momentum_60_5").backtest).to_document(v)
a = audit_leakage(feature_doc=d, backtest_doc=b, filings_doc=[filing_to_dict(f) for f in v.filings], dataset=v, input_sources=frozenset({"price"}))
print(recompute(d["feature"],r,{},v), [(c.check,c.passed) for c in a.checks])
```

### QUANT-3 — Medium: delayed execution records impossible fills in already-delisted names

Locations: `src/research_factory/research/backtest.py:120`, `:123`, `:137`, `:139`, `:153`.

Eligibility is fixed at the decision session, but the engine neither checks execution-day listing/price availability nor rejects unfillable orders. With positive lag a security can delist before execution. It is still recorded as a long/short fill, allocated gross exposure, and charged costs; later missing returns become zero. This is different from the documented simplification of charging turnover when removing an existing delisted holding.

Minimal observed case: security S3 last listed `2024-01-02`; decision `2024-01-02`; fills log says execution `2024-01-03`, short S3, long S0, turnover 1 and cost 0.001. Reproduced on built-in datasets with supported `hold_days=1`: one invalid fill in synthetic:v1 (SYN040, 2023-06-08), and six in edgar-semi:v1 (CELG, XLNX, CTXS, TWTR, BBBY, ATVI). The normal 20-session examples did not exhibit this boundary condition.

Acceptance: define an explicit execution fill policy using only information known at execution. Cancel an untradeable order or otherwise model it as unfilled/cash, with a logged reason and consistent turnover/cost accounting. Do not hindsight-filter it out of the decision universe. Add a delisting-between-decision-and-execution test, including longer delays and existing positions.

```python
import numpy as np
from tests.conftest import tiny_dataset
from tests.test_research import _tiny_table, _spec
from research_factory.research.backtest import run_backtest
v=tiny_dataset(np.zeros((8,4)),listed_to={3:1})
t=_tiny_table(v,[1],np.array([4.,2.,1.,0.]))
b=run_backtest(v,t,_spec(v,hold=10,cost=10.,quantile=.25))
print(v.securities[3].listed_to,b.positions,b.turnover)
```

### QUANT-4 — Low: EDGAR snapshot description and documentary counts overstate precision

Locations: `src/research_factory/data/semi_synthetic.py:3`, `src/research_factory/data/edgar_universe.py:122`, `:181`, `:214`, `docs/architecture.md:129`.

Architecture says 12 exits and 7 IPOs, but the committed snapshot has **10 exits and 8 IPOs** (listed_from after 2019-01-02, including Slack). The module calls listing windows real, but they are filing-date proxies: prospectus date, day before Form 25; fallback rules use 45 days before first periodic report / 10 days before deregistration / 30 days after final report. Revision classification is heuristic (near-integer EPS ratios), not a corporate-action verification. Q4 EPS sometimes uses annual weighted shares rather than quarter weighted shares and 7 records use EPS subtraction. These are described in code/snapshot notes; they should not be represented as exact historical listing status or universally reported quarterly EPS.

Acceptance: fix counts from snapshot metadata and label derived/proxy fields clearly wherever historical authenticity is claimed. Preserve per-value derivation/basis if expanding claims; independently validated event dates and actual quarterly share counts are required for a real-trading dataset. This does not require replacing the intentionally simulated market in v1.

## Intentional scope and optional work, not unimplemented v1 bugs

- Prices and planted signal are simulated by design (ADR-0003); neither accepted committee result nor Sharpe supports an alpha/performance claim on real prices.
- Calendar includes weekdays only, no exchange holidays/early closes; 252 annualization is a convention. Delays are mapped to execution closes in 390-minute buckets, not a minute-bar execution model.
- Constant weights imply uncharged small daily maintenance trades; removal of delisted holdings is charged; final unwind costs are omitted. Explicitly documented in backtest.py:17-22. Broader impact, borrow, financing and liquidity modeling belong to a real-market execution extension.
- EDGAR universe is curated and simulations contain delisted companies. It exercises within-universe survivorship checks; it does not establish a representative all-equity investable universe.
- DSR treats related trials as independent and uses a variance floor; dependence-adjusted effective trial counts are deferred explicitly in ADR-0008. Per-trial return-series storage would enable that future work.
- Licensed vendor adapter is optional RSF-081 under ADR-0007. Adding one would require stronger calendars, event data, numeric data-quality validation, delisting-fill handling and finite-input checks before making real-performance claims.
- No general-purpose feature compiler/optimizer, cross-validation or production alpha research capability is established merely by the current three-feature governance demo.

## Other reviewed boundaries / unpromoted hardening observations

MarketDataset is a frozen dataclass but NumPy buffers and planted metadata remain mutable, while hashes/derived returns are cached; normal callers do not mutate them in the examined pipeline. Numeric data-quality checks emphasize NaN gaps/non-positive prices and do not comprehensively reject all infinity/invalid split cases. Calendar timestamp lookup truncates subsecond instants. These are future data-adapter hardening items; no normal built-in dataset failure was established, so they are not elevated to confirmed production defects here.
