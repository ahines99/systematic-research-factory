# ADR-0003: Real SEC EDGAR filings with semi-synthetic prices

- **Status:** Accepted
- **Date:** 2026-09-23
- **Tickets:** RSF-054, RSF-055, RSF-057, RSF-081

## Context
M6 replaces fixtures with real data. The options for prices were:

- **Free price sources:** usually include only companies that still exist, so survivorship bias is built in. Unofficial sources also carry terms that forbid redistribution. For a project whose premise is point-in-time cleanliness, stamping "this result is biased" on every report undermines the pitch.
- **Paid survivorship-free vendors:** fix the bias, but their licences typically forbid showing the data in a public demo or committing it to a public repository.
- **Synthetic prices:** give up realism, but provide a known right answer, which the evaluation strategy depends on.

The project's purpose is to demonstrate research governance, not to find alpha. Real prices invite "does the signal work?", which is the wrong conversation.

## Decision
1. **Tests and golden cases** stay fully synthetic (RSF-008, RSF-009). These fixtures are deterministic, seeded, and include a planted signal and a planted leak.
2. **Filings and fundamentals are real**, from SEC EDGAR (`submissions` and `companyfacts` APIs, RSF-055). Acceptance time is the knowledge time. Restatements and ticker reuse are handled through the security master (RSF-056).
3. **Prices are semi-synthetic** (RSF-057). Daily prices are simulated for the real EDGAR company universe, keyed by CIK.
   - Returns embed a planted relationship of known strength with a filing-derived feature, and that relationship is **keyed to acceptance time**.
   - A pipeline that leaks by using period-end or filing dates therefore shows a measurable, known inflation of results. The leakage audit is exercised against real filing-timing quirks with a known ground truth.
   - Companies that stopped filing are included and delisted in the simulation, so the universe is survivorship-safe by construction.
   - Corporate actions are simulated, not historical.
4. **Every report and demo screen labels prices as simulated.** No claim is made about real-world signal performance.
5. **A licensed vendor adapter is optional** (RSF-081). It sits behind the same interface for private research use; vendor data never enters the repository or the public demo.

## Alternatives considered
- **Free price data with a stated bias:** rejected because it undermines the project's premise, and because of redistribution terms.
- **Paid vendor as the primary source:** rejected for v1 because of cost, and because it can't be shown publicly. Kept as the optional RSF-081.
- **Fully synthetic data everywhere:** rejected because real EDGAR timing (acceptance times, amendments, restatements) is where the most interesting point-in-time engineering lives.

## Consequences
- The public demo and repository contain only redistributable data: SEC filings, which are public, and generated prices.
- Evaluation keeps a known right answer even on real filings.
- Point-in-time problems on the price side (split and dividend adjustment histories, symbol changes in price feeds) are exercised only with synthetic data until RSF-081.
- The project cannot say whether any real signal works, which is intentional.

## Revisit when
A licensed dataset with public-display rights becomes affordable, or the project's goal shifts from demonstrating governance to running real research.
