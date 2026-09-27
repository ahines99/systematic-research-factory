# Data and methodology sheet

Version 1, 2026-09-27. **All prices are simulated.** Two datasets serve different purposes; the simulation study does not use the SEC sample as unseen validation data.

| Property | Fully synthetic study | SEC-timed demonstration |
|---|---|---|
| Companies | 50 generated securities | 44 curated companies |
| Filing inputs | Generated EPS, acceptance times and revisions; 2017 warm-up | 1,325 SEC-derived filing/version records, 2019–2023 |
| Membership | Six exits, five IPOs in the generated universe | Ten exits, eight IPOs; listing windows inferred from filings |
| Prices | Generated market/idiosyncratic returns, acceptance-timed jump and drift | Simulated prices aligned to real filing timing |
| Purpose | Coupled negative/planted/leakage controls across seeds | Real-source provenance and availability handling |
| Main limit | Known generator and deliberately planted effect | Curated sample, proxy membership and derived EPS |

The SEC sample is not a representative, survivorship-complete exchange universe. Prospectus/Form 25 dates and documented fallback offsets approximate listing windows. Q4 EPS can be derived using annual weighted shares; seven records use EPS subtraction. Ratio heuristics classify revisions without independently verifying corporate actions. SEC provenance must not be translated into a claim that every value is a directly reported quarterly EPS figure. See [ADR-0003](../adr/0003-market-data-semi-synthetic.md) and the committed snapshot's provenance records.

The provider obtains public submissions and XBRL facts through the [SEC APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces). The application uses accession-linked acceptance times and versioned records, rather than assuming a fiscal period's result was available at its period end. Each feature records the input evidence and knowledge time. A thirty-minute ingestion lag and next-close execution are conservative modeling choices, not measurements of every vendor's availability or a guarantee of executable prices.

The EPS-growth feature compares a known current quarter with the prior-year quarter; missing or stale inputs produce no signal. It is not standardized unexpected earnings relative to analysts' forecasts. Ranks form equal-weight tails with 0.5 exposure per side. Prices use planted effects at acceptance time so deliberately using period-end values creates a meaningful invalid counterfactual. The null control removes the planted jump/drift but retains the rest of the generator.

Simulation uses weekday sessions including exchange holidays. It standardizes shocks using the generated event population and does not model a real information vendor, exchange calendar, borrow availability, liquidity, impact, dynamic weight drift costs, or terminal liquidation. Exits in the SEC-timed sample do not inject a hindsight penalty for failed companies. Do not infer real investment returns, execution capacity, empirical PEAD, or broad statistical calibration from these artifacts.

Reproduction is offline from committed/generated inputs. Fresh external SEC ingestion requires a declared user agent and is a separate provenance event; never overwrite the study's original snapshot or expectations with newly downloaded data. The [protocol](protocol.md), [research note](note.md), raw JSON and CSV identify what was actually measured.
