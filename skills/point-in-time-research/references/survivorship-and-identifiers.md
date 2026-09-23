# Survivorship, identifiers and corporate actions

This file supports the `point-in-time-research` Skill. In this project, prices, delistings and
corporate actions are **simulated** for the real EDGAR company universe (ADR-0003). The same rules
apply to a licensed vendor feed if one is added later (RSF-081).

## 1. Survivorship bias

**What it is:** building the universe from companies that exist *today* (`universe mode:
current_constituents`). The backtest never holds the companies that later failed, were acquired
cheaply or were delisted. Those are often exactly the names a value, distress or accruals signal
would have bought or shorted.

**Rules**
- [ ] The universe at decision time D comes from `get_universe_as_of(as_of=D)` (`point_in_time`).
  It includes names that later delisted.
- [ ] Membership filters (exchange, share type, minimum price, minimum market cap) are evaluated
  with data known **at D**, not with today's attributes.
- [ ] Names that enter the universe after D (IPOs, later listings) are excluded at D.
- [ ] The number of names per date rises and falls over time. A flat count is a warning sign.

**How to check it**
- Ask `get_universe_as_of` for a date early in the sample and a date late in the sample. Some
  names in the early universe should be missing from the late one. If none are, ask for evidence.
- In the backtest artifact, confirm that delisted names had positions before their delisting date.

## 2. Delistings and delisting returns

A delisted position has to realize a **final return**: the move from the last regular price to the
value holders actually got (cash in a merger, the price on another venue, or close to zero in a
bankruptcy).

- Dropping the position on its last trading day with no final return treats the exit as free.
  For performance-related delistings (bankruptcy, failing listing standards) this biases long
  returns **up** and short returns **down**. Shumway (1997), "The Delisting Bias in CRSP Data"
  (*Journal of Finance*), documents that delisting returns are often missing in exactly these cases.
- Merger delistings usually have a *positive* final return, from the takeover premium, which is
  largely realized before the delisting date.
- In the factory's simulation, companies that stopped filing are delisted by construction. Check
  that the backtest artifact shows a delisting return for each, and that no position stays open
  after delisting.
- If a delisting return is missing, the run needs a stated, conservative assumption. It must not
  quietly use zero. Record it as an assumption with evidence, or as `NEEDS_EVIDENCE`.

## 3. Identifiers

| Identifier | Scope | Stable? | Use |
|---|---|---|---|
| CIK | SEC filer (issuer or person) | **Yes.** Assigned once and never reused for another entity | Primary key for fundamentals and the issuer |
| Ticker | Exchange listing | **No.** Changes, and is reused for unrelated companies | Display, and joining vendor data *as of a date* |
| Company name | Filer | No. Renames keep the CIK (`formerNames` in the submissions API) | Display only |
| Security-level ID (security master) | One listed share class | Stable within this system | Positions and prices (RSF-056) |

**Traps**
- **Ticker reuse:** after a company delists, its ticker can go to an unrelated issuer. A join on
  ticker alone attaches one company's filings to another company's prices. Resolve
  ticker → CIK **as of D**, and never through a mapping that took effect after D (RSF-056).
- **Current ticker files are not point-in-time.** SEC's ticker-to-CIK file and the submissions
  `tickers` field show today's mapping only.
- **One CIK, several securities:** an issuer with several listed share classes has one CIK and
  several securities. Fundamentals are per issuer, but prices and market cap are per security or
  summed. Say which one the feature uses.
- **The business moves, the CIK stays behind:** a holding-company reorganization, redomicile or
  spin-off can put the same economic business under a *new* CIK. Link predecessor and successor
  explicitly in the security master. Don't assume the history carries across.
- **Mergers:** the target's CIK stops filing. The acquirer's fundamentals jump at the close date.
  Growth features computed across that jump are artificial.

## 4. Corporate actions

| Action | Return treatment | Level and fundamentals trap |
|---|---|---|
| Split / reverse split | No economic return. Adjust the price series | Adjusted price *levels* before the split carry **future** split information. A "price > $5" filter or a market cap built from them is a look-ahead. Use unadjusted price × shares outstanding known at D |
| Cash dividend | Total return includes it on the ex-date | Price-only returns understate high-yield names. Use total return, and say so |
| Spin-off | The parent's price drop on the ex-date is not a loss. Include the value of the distributed shares | The parent's fundamentals change at the spin. The spin-off gets a new CIK |
| Stock or cash merger | Terminal value = consideration received | See identifiers above |
| Share issuance / buyback | Not a return event | Shares outstanding for market cap should come from filings (e.g. `dei:EntityCommonStockSharesOutstanding` on the cover page), known from acceptance time |

**Per-share data across splits:** EPS and other per-share values in filings are in the share terms
of *that* filing, and later filings restate comparatives for splits. Per-share values compared over
time must be put in consistent terms using **only splits effective and known by D**. Otherwise a
split announced after D leaks into the history.

**Adjustment factors:** a return from t−1 to t that is adjusted using the actions between t−1 and
t is point-in-time clean. A back-adjusted *level* series is not clean for anything except computing
returns.

## 5. Trading calendar alignment
- Filing events, price bars and decision times all have to sit on the same exchange calendar,
  including holidays and early closes. Forward-filling a value over a holiday is fine. Moving an
  event *backwards* to the previous session is a leak.
- The return window for a decision at D begins at `D + execution_delay_minutes`. The price that
  starts that window is the first one observable at or after that time, never the price at D
  when a delay is specified.
