"""Security master and EDGAR universe builder (RSF-056, ADR-0003).

CIK is the permanent identifier. Tickers are curated with effective dates because EDGAR
only reports a company's *current* tickers (and none for companies that stopped filing).
Listing windows are derived from filings: IPOs from the first final prospectus (424B4),
exits from exchange delisting notices (Form 25) or deregistrations (Form 15).

The universe deliberately includes companies that were acquired or failed during the
sample, so a point-in-time universe differs from today's survivors.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from ..domain.identity import canonical_json
from .edgar import (
    NET_INCOME_CONCEPTS,
    SHARE_CONCEPTS,
    EdgarClient,
    EpsFact,
    FilingMeta,
    parse_concept_facts,
    parse_eps_facts,
    parse_submissions,
)
from .world import Filing, Security, TickerInterval

WINDOW_START = date(2019, 1, 2)
WINDOW_END = date(2023, 12, 29)
HISTORY_START = date(2016, 10, 1)
PERIODIC = {"10-Q", "10-K", "10-Q/A", "10-K/A"}


@dataclass(frozen=True)
class Member:
    cik: int
    expected_name: str  # substring check against EDGAR's name, guards against a wrong CIK
    tickers: tuple[tuple[str, str | None, str | None], ...]  # (ticker, start, end) ISO dates
    exit_kind: str | None = None  # "acquired" | "failed" | "taken_private"
    note: str = ""


def _t(ticker: str, start: str | None = None, end: str | None = None) -> tuple[str, str | None, str | None]:
    return (ticker, start, end)


UNIVERSE: tuple[Member, ...] = (
    Member(320193, "Apple", (_t("AAPL"),)),
    Member(789019, "MICROSOFT", (_t("MSFT"),)),
    Member(1018724, "AMAZON", (_t("AMZN"),)),
    Member(1652044, "Alphabet", (_t("GOOGL"),)),
    Member(
        1326801,
        "Meta Platforms",
        (_t("FB", None, "2022-06-08"), _t("META", "2022-06-09")),
        note="ticker change FB -> META",
    ),
    Member(1045810, "NVIDIA", (_t("NVDA"),)),
    Member(19617, "JPMORGAN", (_t("JPM"),)),
    Member(200406, "JOHNSON & JOHNSON", (_t("JNJ"),)),
    Member(80424, "PROCTER & GAMBLE", (_t("PG"),)),
    Member(34088, "EXXON", (_t("XOM"),)),
    Member(104169, "Walmart", (_t("WMT"),)),
    Member(354950, "HOME DEPOT", (_t("HD"),)),
    Member(21344, "COCA COLA", (_t("KO"),)),
    Member(77476, "PEPSICO", (_t("PEP"),)),
    Member(50863, "INTEL", (_t("INTC"),)),
    Member(858877, "CISCO", (_t("CSCO"),)),
    Member(78003, "PFIZER", (_t("PFE"),)),
    Member(310158, "Merck", (_t("MRK"),)),
    Member(1341439, "ORACLE", (_t("ORCL"),)),
    Member(796343, "ADOBE", (_t("ADBE"),)),
    Member(1065280, "NETFLIX", (_t("NFLX"),)),
    Member(1108524, "Salesforce", (_t("CRM"),)),
    Member(909832, "COSTCO", (_t("COST"),)),
    Member(320187, "NIKE", (_t("NKE"),)),
    Member(63908, "MCDONALDS", (_t("MCD"),)),
    Member(93410, "CHEVRON", (_t("CVX"),)),
    Member(732712, "VERIZON", (_t("VZ"),)),
    # Initial public offerings and direct listings inside the window.
    Member(1543151, "Uber", (_t("UBER"),)),
    Member(1585521, "Zoom", (_t("ZM"),)),
    Member(1506293, "Pinterest", (_t("PINS"),)),
    Member(1640147, "Snowflake", (_t("SNOW"),)),
    Member(1792789, "DoorDash", (_t("DASH"),)),
    Member(1679788, "Coinbase", (_t("COIN"),), note="direct listing (no 424B4 prospectus)"),
    Member(1874178, "Rivian", (_t("RIVN"),)),
    # Companies that stopped trading inside the window.
    Member(1418091, "Twitter", (_t("TWTR"),), "taken_private"),
    Member(718877, "ACTIVISION", (_t("ATVI"),), "acquired"),
    Member(743988, "XILINX", (_t("XLNX"),), "acquired"),
    Member(98246, "TIFFANY", (_t("TIF"),), "acquired"),
    Member(1087423, "RED HAT", (_t("RHT"),), "acquired"),
    Member(816284, "CELGENE", (_t("CELG"),), "acquired"),
    Member(886158, "BED BATH", (_t("BBBY"),), "failed"),
    Member(719739, "SVB FINANCIAL", (_t("SIVB"),), "failed"),
    Member(1764925, "Slack", (_t("WORK"),), "acquired"),
    Member(877890, "CITRIX", (_t("CTXS"),), "taken_private"),
)

# Exits are price-neutral: the only planted effect is the acceptance-timed signal (audit Q7).
EXIT_RETURNS = {"acquired": 0.0, "taken_private": 0.0, "failed": 0.0}


def _next_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _prev_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def listing_window(filings: list[FilingMeta], member: Member) -> tuple[date, date | None, str]:
    """(listed_from, listed_to, how) derived from the filing history."""
    how = []
    prospectus = [
        f.filing_date
        for f in filings
        if f.form == "424B4" and f.filing_date >= WINDOW_START - timedelta(days=30)
    ]
    periodic = [f for f in filings if f.form in PERIODIC]
    listed_from = WINDOW_START
    if prospectus:
        listed_from = max(WINDOW_START, _next_weekday(min(prospectus)))
        how.append("listed from final prospectus (424B4) date")
    elif periodic and min(f.filing_date for f in periodic) > WINDOW_START + timedelta(days=60):
        first = min(f.filing_date for f in periodic)
        listed_from = _next_weekday(first - timedelta(days=45))
        how.append("listed about 45 days before the first periodic report (no prospectus)")
    listed_to: date | None = None
    if member.exit_kind:
        delist = [
            f.filing_date for f in filings if f.form in ("25", "25-NSE") and f.filing_date >= WINDOW_START
        ]
        dereg = [
            f.filing_date
            for f in filings
            if f.form in ("15-12B", "15-12G", "15-15D") and f.filing_date >= WINDOW_START
        ]
        if delist:
            listed_to = _prev_weekday(min(delist) - timedelta(days=1))
            how.append("delisted the day before the Form 25 delisting notice")
        elif dereg:
            listed_to = _prev_weekday(min(dereg) - timedelta(days=10))
            how.append("delisted 10 days before the Form 15 deregistration")
        elif periodic:
            listed_to = _prev_weekday(max(f.filing_date for f in periodic) + timedelta(days=30))
            how.append("delisted 30 days after the last periodic report")
        if listed_to is not None and listed_to > WINDOW_END:
            listed_to = None
    return listed_from, listed_to, "; ".join(how) or "listed throughout the window"


QUARTER_DAYS = (80, 100)
ANNUAL_DAYS = (350, 380)


def period_label(end: date) -> str:
    """Quarters are identified by their period end, not by companyfacts' fy/fp labels (audit Q3).

    Ten days are subtracted so 52/53-week quarters ending in the first days of a month
    (e.g. 2022-01-02 or 2022-01-30 for a January year end) keep a stable month.
    """
    return (end - timedelta(days=10)).strftime("P%Y-%m")


def _within(fact: EpsFact, bounds: tuple[int, int]) -> bool:
    return fact.days is not None and bounds[0] <= fact.days <= bounds[1]


def classify_revision(old: float, new: float) -> str | None:
    """None for rounding noise; "split_adjusted" for integer re-basing; otherwise "restated" (audit Q6)."""
    if abs(new - old) <= max(0.015, 0.01 * abs(old)):
        return None
    if old and new:
        for ratio in (old / new, new / old):
            k = round(ratio)
            if k >= 2 and abs(ratio - k) <= 0.03 * k:
                return "split_adjusted"
    return "restated"


@dataclass
class ExtractionReport:
    counts: dict[str, int] = field(default_factory=dict)

    def bump(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1


def extract_with_report(
    cik: int,
    filings: list[FilingMeta],
    eps: list[EpsFact],
    net_income: list[EpsFact] = (),  # type: ignore[assignment]
    shares: list[EpsFact] = (),  # type: ignore[assignment]
) -> tuple[list[Filing], ExtractionReport]:
    """Point-in-time quarterly EPS versions from periodic filings.

    * Quarters are keyed by period end (``period_label``).
    * Three-month comparatives in a filing are processed first: they introduce unknown
      periods (e.g. pre-IPO quarters) and re-based or restated versions of known ones.
    * A 10-Q's own three-month EPS is the original value of its quarter.
    * Fiscal Q4: the 10-K's own three-month EPS when reported; otherwise Q4 net income
      (annual minus the three known quarters) over the year's weighted-average shares.
      Net income is additive and unaffected by stock splits, unlike EPS (audit Q2).
      Only when net income is unavailable is EPS subtracted, with a plausibility check.
    * After a split, the 10-K's prior-year comparatives re-base the prior year's Q4.
    """
    sid = f"CIK{cik:010d}"
    report = ExtractionReport()

    def group(facts: list[EpsFact]) -> dict[str, list[EpsFact]]:
        out: dict[str, list[EpsFact]] = {}
        for fact in facts:
            out.setdefault(fact.accession, []).append(fact)
        return out

    eps_by, ni_by, sh_by = group(eps), group(list(net_income)), group(list(shares))
    known_eps: dict[str, float] = {}
    known_end: dict[str, date] = {}
    original: dict[str, str] = {}
    known_ni: dict[tuple[date | None, date], float] = {}
    used_accessions: set[str] = set()
    out: list[Filing] = []

    def add(end: date, value: float, meta: FilingMeta, comparative: bool) -> None:
        label = period_label(end)
        value = round(value, 4)
        previous = known_eps.get(label)
        kind = "original" if previous is None else classify_revision(previous, value)
        if kind is None:
            if previous is not None and previous != value:
                report.bump("rounding_ignored")
            return
        accession = f"{meta.accession}#{label}" if comparative else meta.accession
        if accession in used_accessions:
            return
        used_accessions.add(accession)
        amends = original.get(label) if previous is not None else None
        if previous is None:
            original[label] = accession
        known_eps[label] = value
        known_end[label] = end
        report.bump(kind)
        out.append(
            Filing(
                accession=accession,
                security_id=sid,
                form=f"{meta.form} comparative" if comparative else meta.form,
                fiscal_period=label,
                period_end=end,
                filed_date=meta.filing_date,
                accepted_at=meta.accepted_at,
                eps=value,
                amends=amends,
                revision=kind,
            )
        )

    def quarters_of_year(start: date, end: date) -> list[tuple[date, float]]:
        """Known quarterly net income inside a fiscal year, excluding its last quarter."""
        found: dict[date, float] = {}
        for (q_start, q_end), value in known_ni.items():
            if q_start is None or not 80 <= (q_end - q_start).days <= 100:
                continue
            if q_start >= start - timedelta(days=7) and q_end <= end - timedelta(days=60):
                found[q_end] = value
        return sorted(found.items())

    def derive_q4(
        annual_ni: EpsFact | None, annual_sh: EpsFact | None, annual_eps: EpsFact | None
    ) -> tuple[float, str] | None:
        if (
            annual_ni is not None
            and annual_sh is not None
            and annual_ni.start is not None
            and annual_sh.value > 0
        ):
            implied = annual_ni.value / annual_sh.value
            # Units guard: some filers tag shares in millions. Net income over shares must match
            # the reported annual EPS, or the net-income path is not trusted.
            consistent = annual_eps is None or abs(implied - annual_eps.value) <= 0.1 * max(
                abs(annual_eps.value), 0.1
            )
            quarters = quarters_of_year(annual_ni.start, annual_ni.end)
            if consistent and len(quarters) == 3:
                return (annual_ni.value - sum(v for _, v in quarters)) / annual_sh.value, "q4_from_net_income"
            if not consistent:
                report.bump("q4_net_income_inconsistent")
        if annual_eps is not None and annual_eps.start is not None:
            parts = [
                known_eps[label]
                for label, q_end in known_end.items()
                if annual_eps.start < q_end <= annual_eps.end - timedelta(days=60)
            ]
            if len(parts) == 3:
                q4 = annual_eps.value - sum(parts)
                plausible = (
                    abs(q4) <= 3 * max(abs(p) for p in parts) + 0.5
                    and abs(q4) <= 2 * abs(annual_eps.value) + 0.5
                )
                if plausible:
                    return q4, "q4_from_eps"
        return None

    last_useful = datetime.combine(WINDOW_END + timedelta(days=7), datetime.min.time(), tzinfo=UTC)
    for meta in filings:
        if meta.form not in PERIODIC or meta.report_date is None or meta.report_date < HISTORY_START:
            continue
        if meta.accepted_at > last_useful:
            break  # knowable only after the sample ends
        here_eps = eps_by.get(meta.accession, [])
        here_ni = ni_by.get(meta.accession, [])
        here_sh = sh_by.get(meta.accession, [])
        for fact in here_ni:
            if _within(fact, QUARTER_DAYS) or _within(fact, ANNUAL_DAYS):
                known_ni[(fact.start, fact.end)] = fact.value

        for fact in sorted(here_eps, key=lambda f: f.end):  # comparatives first
            if _within(fact, QUARTER_DAYS) and fact.end != meta.report_date:
                add(fact.end, fact.value, meta, comparative=True)

        own_quarter = next(
            (f for f in here_eps if _within(f, QUARTER_DAYS) and f.end == meta.report_date), None
        )
        if meta.form.startswith("10-Q"):
            if own_quarter is not None:
                add(own_quarter.end, own_quarter.value, meta, comparative=False)
            continue

        # 10-K / 10-K/A
        if own_quarter is not None:
            add(own_quarter.end, own_quarter.value, meta, comparative=False)
            report.bump("q4_reported")
        else:

            def annual(facts: list[EpsFact], end: date) -> EpsFact | None:
                return next(
                    (f for f in facts if _within(f, ANNUAL_DAYS) and abs((f.end - end).days) <= 3), None
                )

            derived = derive_q4(
                annual(here_ni, meta.report_date),
                annual(here_sh, meta.report_date),
                annual(here_eps, meta.report_date),
            )
            if derived is None:
                report.bump("q4_skipped")
            else:
                add(meta.report_date, derived[0], meta, comparative=False)
                report.bump(derived[1])
            # Re-base last year's Q4 with this 10-K's prior-year comparatives (they reflect any split).
            prior_end = meta.report_date - timedelta(days=364)
            prior_ni, prior_sh = annual(here_ni, prior_end), annual(here_sh, prior_end)
            if prior_ni is not None and prior_sh is not None and period_label(prior_ni.end) in known_eps:
                rebased = derive_q4(prior_ni, prior_sh, None)
                if rebased is not None:
                    add(prior_ni.end, rebased[0], meta, comparative=True)
    return out, report


def extract_filings(
    cik: int,
    filings: list[FilingMeta],
    facts: list[EpsFact],
    net_income: list[EpsFact] = (),  # type: ignore[assignment]
    shares: list[EpsFact] = (),  # type: ignore[assignment]
) -> list[Filing]:
    return extract_with_report(cik, filings, facts, net_income, shares)[0]


def build_universe(client: EdgarClient, members: tuple[Member, ...] = UNIVERSE) -> dict[str, Any]:
    securities: list[dict[str, Any]] = []
    filings: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    extraction: dict[str, int] = {}
    for m in members:
        pages = client.submissions(str(m.cik))
        facts_doc = client.companyfacts(str(m.cik))
        sub = pages[0].json()
        names = [sub["name"], *(n.get("name", "") for n in sub.get("formerNames", []))]
        matching = [n for n in names if m.expected_name.lower() in n.lower()]
        if not matching:
            raise ValueError(f"CIK {m.cik} is {sub['name']!r}, expected {m.expected_name!r}")
        name = matching[0]  # the name the company traded under, even if EDGAR has renamed the entity
        metas = parse_submissions([p.json() for p in pages])
        listed_from, listed_to, how = listing_window(metas, m)
        facts_json = facts_doc.json()
        extracted, rep = extract_with_report(
            m.cik,
            metas,
            parse_eps_facts(facts_json),
            parse_concept_facts(facts_json, NET_INCOME_CONCEPTS, "USD"),
            parse_concept_facts(facts_json, SHARE_CONCEPTS, "shares"),
        )
        for key, value in rep.counts.items():
            extraction[key] = extraction.get(key, 0) + value
        sid = f"CIK{m.cik:010d}"
        tickers = []
        for ticker, start, end in m.tickers:
            t_start = date.fromisoformat(start) if start else listed_from
            t_end = date.fromisoformat(end) if end else listed_to
            tickers.append(
                {"ticker": ticker, "start": t_start.isoformat(), "end": t_end.isoformat() if t_end else None}
            )
        securities.append(
            {
                "security_id": sid,
                "cik": m.cik,
                "name": name,
                "listed_from": listed_from.isoformat(),
                "listed_to": listed_to.isoformat() if listed_to else None,
                "listing_basis": how,
                "exit_kind": m.exit_kind if listed_to else None,
                "delisting_return": EXIT_RETURNS[m.exit_kind] if m.exit_kind and listed_to else None,
                "tickers": tickers,
                "note": m.note,
            }
        )
        filings.extend(
            {
                "accession": f.accession,
                "security_id": f.security_id,
                "form": f.form,
                "fiscal_period": f.fiscal_period,
                "period_end": f.period_end.isoformat(),
                "filed_date": f.filed_date.isoformat(),
                "accepted_at": f.accepted_at.isoformat(),
                "eps": f.eps,
                "amends": f.amends,
                "revision": f.revision,
            }
            for f in extracted
        )
        for page in [*pages, facts_doc]:
            provenance.append({"cik": m.cik, "url": page.url, "sha256": page.content_hash})
    return {
        "format": "rsf-edgar-universe/1",
        "built_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "SEC EDGAR submissions and companyfacts APIs (public domain)",
        "window": {"start": WINDOW_START.isoformat(), "end": WINDOW_END.isoformat()},
        "securities": securities,
        "filings": sorted(filings, key=lambda f: (f["accepted_at"], f["accession"])),
        "provenance": provenance,
        "extraction": dict(sorted(extraction.items())),
        "notes": [
            "EPS is the XBRL basic EPS (falling back to diluted) for three-month periods.",
            "Quarters are keyed by period end (label PYYYY-MM), not by companyfacts fy/fp.",
            "Fiscal Q4 EPS is the reported three-month value when present; otherwise Q4 net income "
            "(annual minus Q1-Q3 known at the 10-K) over the year's weighted-average basic shares.",
            "Later three-month comparatives create versions tagged split_adjusted or restated; "
            "differences within one cent or 1% are treated as rounding.",
            "Exits are price-neutral; tickers are curated because EDGAR reports only current tickers.",
        ],
    }


def write_snapshot(doc: dict[str, Any], path: Any) -> None:
    with open(path, "wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(canonical_json(doc))


def read_snapshot(path: Any) -> dict[str, Any]:
    with gzip.open(path, "rb") as fh:
        doc: dict[str, Any] = json.loads(fh.read())
    return doc


def securities_and_filings(doc: dict[str, Any]) -> tuple[tuple[Security, ...], tuple[Filing, ...]]:
    from .world import filing_from_dict

    secs = tuple(
        Security(
            security_id=s["security_id"],
            name=s["name"],
            listed_from=date.fromisoformat(s["listed_from"]),
            listed_to=date.fromisoformat(s["listed_to"]) if s["listed_to"] else None,
            delisting_return=s["delisting_return"],
            tickers=tuple(
                TickerInterval(
                    t["ticker"],
                    date.fromisoformat(t["start"]),
                    date.fromisoformat(t["end"]) if t["end"] else None,
                )
                for t in s["tickers"]
            ),
        )
        for s in doc["securities"]
    )
    return secs, tuple(filing_from_dict(f) for f in doc["filings"])
