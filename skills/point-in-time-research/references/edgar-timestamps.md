# EDGAR timestamps: what was knowable, and when

This file supports the `point-in-time-research` Skill. The authoritative API documentation is
SEC, "EDGAR Application Programming Interfaces":
https://www.sec.gov/search-filings/edgar-application-programming-interfaces

The factory reads EDGAR through `get_filings_as_of`. This note explains what that tool has to get
right, so a reviewer can tell when its output, or a feature spec, is wrong.

## 1. The three dates on a periodic report

| Field | Example | Meaning |
|---|---|---|
| `reportDate` (submissions) / `end` (XBRL fact) | 2024-03-31 | End of the fiscal period the numbers describe |
| `filingDate` (submissions) / `filed` (XBRL fact) | 2024-05-02 | The *official filing date* that EDGAR assigns. Date only |
| `acceptanceDateTime` (submissions) | 2024-05-02 16:31:07 ET | When EDGAR accepted the submission. The earliest time the public could know it |

**Knowledge time = acceptance time.** Period end comes weeks or months too early. Filing date has
no time of day, and it is assigned by rule, so it does not mark when the information became public.

### Why `filingDate` is not a knowledge time
- EDGAR accepts transmissions on business days from 6:00 a.m. to 10:00 p.m. ET. Under Regulation
  S-T Rule 13, a submission that starts after **5:30 p.m. ET** generally gets the *next business
  day* as its filing date. Some forms are exceptions: Section 16 Forms 3, 4 and 5 are deemed filed
  the same day until 10:00 p.m.
- So acceptance at 16:31 has the same-day filing date, but it came *after* the 16:00 close. Using
  the filing date at that day's close leaks by 31 minutes.
- Acceptance at 18:10 on Monday gets Tuesday's filing date. Here the filing date comes *after*
  the knowledge time, which is conservative but inaccurate.
- The error from `filingDate` has no consistent sign, so it can't be fixed with a fixed lag.

## 2. Submissions API (the source of acceptance times)

`https://data.sec.gov/submissions/CIK##########.json` (CIK zero-padded to 10 digits)

- `filings.recent` is a set of parallel arrays, with one index per filing: `accessionNumber`,
  `filingDate`, `reportDate`, `acceptanceDateTime`, `form`, `primaryDocument`, `isXBRL`,
  `isInlineXBRL`, and so on.
- `recent` holds at least the last year of filings, or the last 1,000, whichever is more. Older
  filings are in extra JSON files listed under `filings.files`. **Fetch all of them.** Otherwise the
  history silently loses its early filings.
- Company-level fields (`name`, `tickers`, `exchanges`, `formerNames`) describe the company
  **today**. `tickers` is not a historical mapping (see
  [survivorship-and-identifiers.md](survivorship-and-identifiers.md)).

### Time zone of `acceptanceDateTime`
The JSON gives values such as `2024-05-02T20:31:07.000Z`, and the trailing `Z` is correct: the
value is **UTC**. This was verified on 2026-09-23 against 3,005 filings from three filers. EDGAR
accepts filings from 06:00 to 22:00 Eastern, and the observed label hours span 10:00–02:00, which is
that window shifted by the 4–5 hour UTC offset. Filings stamped with the next business day's filing
date begin at 21:30Z, which is EDGAR's 17:30 Eastern cutoff. (The `<ACCEPTANCE-DATETIME>` in a
filing's SGML header, `YYYYMMDDhhmmss`, is Eastern wall-clock time; don't mix the two sources.)

1. Parse the value as UTC.
2. Convert to `America/New_York` (IANA zone, so daylight saving is handled) only to reason about
   sessions, e.g. whether the filing arrived before the 16:00 close.
3. Store it timezone-aware.

If you get this wrong, every knowledge time is 4–5 hours off. Treating a UTC value as Eastern makes
filings look *later* than they were; treating an Eastern header value as UTC makes them look
*earlier*, which hides after-close leaks. If a new data source disagrees, re-run the hour-distribution
check above before trusting it.

## 3. XBRL companyfacts (the source of values)

`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

Structure: `facts → taxonomy (us-gaap, dei, ...) → concept → units → unit → [fact, ...]`. Each fact
has `end`, `val`, `accn`, `fy`, `fp`, `form`, `filed`, `start` for duration facts, and sometimes `frame`.

Rules:
1. **`filed` is a date only.** Get the knowledge time by joining `accn` to the submissions
   `accessionNumber` (both use the `0000000000-YY-NNNNNN` format) and taking that filing's
   `acceptanceDateTime`.
2. **The same period appears many times.** A fiscal-2023 revenue fact appears in the FY2023 10-K,
   again as a comparative in the FY2024 10-K, and possibly restated. Keep *every* version, keyed
   by `(concept, unit, start, end)`, each with its own acceptance time.
3. **Choosing a value at decision time D:** from the versions with `knowledge_ts <= D`, take the one
   with the latest `knowledge_ts`. Taking the latest version overall is `timing_basis:
   latest_restated`, a restatement look-ahead.
4. **`fy` and `fp` describe the filing, not the fact.** A prior-year comparative carries the new
   filing's `fy`. Identify periods by `start` and `end`.
5. **`frame` and the frames API are not point-in-time.** SEC documents that frames return, for each
   entity, the one fact that was *last filed* and most closely fits the calendar period. That is a
   latest-restated view.
6. **Duration facts:** 10-Qs report quarter and year-to-date durations, and fourth-quarter values
   are often only implied (full year minus 9-month YTD). A derived value's knowledge time is the
   **latest** knowledge time among its inputs.
7. **Instant vs duration:** balance-sheet facts have no `start`. Don't average an instant with a
   duration without matching the periods.

## 4. Amendments, restatements and related events

| Event | Form or signal | How to handle it at a point in time |
|---|---|---|
| Full amendment with restated financial statements | `10-K/A`, `10-Q/A` | New fact versions known from the **amendment's** acceptance time. Earlier decisions keep the original values |
| Partial amendment (e.g. only Part III, filed after the proxy) | `10-K/A` | Often has no financial statements, so there are no new financial facts. Don't treat it as a restatement |
| Revision through comparatives ("little r") | Next `10-Q` / `10-K` with changed prior-period values | Same as rule 3 in section 3: new version from the later filing's acceptance time |
| Non-reliance notice | `8-K` Item 4.02 | A dated event. Before it, the original numbers were what the market knew |
| Late filing notice | `NT 10-K`, `NT 10-Q` | A dated event, and itself possibly informative. The missing report is not known until it is accepted |
| Earnings release before the 10-Q | `8-K` Item 2.02 (press release, often Exhibit 99.1) | Headline numbers were public earlier than the 10-Q. Using 10-Q acceptance is conservative, not a leak, but for announcement-driven hypotheses it understates how fast the signal is. Pick one deliberately and record it in the frozen hypothesis |

Using the latest restated value everywhere tends to make accounting signals look better, because
a restatement is itself usually bad news that arrives later.

## 5. From acceptance time to the first tradable decision

1. Convert `acceptanceDateTime` to a timezone-aware time in `America/New_York`.
2. On the exchange calendar (weekends, holidays, 13:00 ET early closes), find the first scheduled
   `decision_ts` with `decision_ts >= knowledge_ts`.
3. The trade happens at `decision_ts + execution_delay_minutes`. The return window starts then.

| Accepted (ET) | Close-decision strategy (16:00) | Note |
|---|---|---|
| Tue 08:05 | Tue close | Pre-market acceptance, same-day close |
| Tue 15:59 | Tue close | Allowed by the rule, but only one minute to react. The execution delay has to be realistic |
| Tue 16:31 | Wed close | After the close, next session |
| Tue 18:10 (filing date Wed) | Wed close | Filing date and first session agree here, by coincidence |
| Fri 17:00 before a Monday holiday | Tue close | Calendar-aware roll |
| 13:30 on an early-close day | Next session | That day's close is 13:00, not 16:00 |

## 6. Fair access (for whoever builds the adapter)

- Declare a `User-Agent` that says who you are and how to reach you, in the format SEC shows, e.g.
  `Sample Company Name AdminContact@<sample company domain>.com`. Put the real value in
  configuration, never in a Skill or in code.
- Stay under SEC's published limit of **10 requests per second** across all threads. Heavier
  traffic can get the client temporarily blocked.
- Cache responses (the factory stores evidence by content hash). Bulk archives
  (`submissions.zip`, `companyfacts.zip`) are rebuilt nightly and suit backfills better than
  many single requests.
- A block or outage shows up as `UPSTREAM_UNAVAILABLE`. The correct result is `NEEDS_EVIDENCE`,
  never a fallback to stale or made-up data.
