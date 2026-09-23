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
from .edgar import EdgarClient, EpsFact, FilingMeta, parse_eps_facts, parse_submissions
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
    Member(1326801, "Meta Platforms", (_t("FB", None, "2022-06-08"), _t("META", "2022-06-09")), note="ticker change FB -> META"),
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

EXIT_RETURNS = {"acquired": 0.0, "taken_private": 0.0, "failed": -0.9}


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
    prospectus = [f.filing_date for f in filings if f.form == "424B4" and f.filing_date >= WINDOW_START - timedelta(days=30)]
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
        delist = [f.filing_date for f in filings if f.form in ("25", "25-NSE") and f.filing_date >= WINDOW_START]
        dereg = [f.filing_date for f in filings if f.form in ("15-12B", "15-12G", "15-15D") and f.filing_date >= WINDOW_START]
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


def _quarter_number(fp: str | None) -> int | None:
    return {"Q1": 1, "Q2": 2, "Q3": 3, "FY": 4}.get(fp or "")


@dataclass
class _Known:
    label_by_end: dict[date, str] = field(default_factory=dict)
    value: dict[str, float] = field(default_factory=dict)
    original: dict[str, str] = field(default_factory=dict)  # label -> accession of first version


def extract_filings(cik: int, filings: list[FilingMeta], facts: list[EpsFact]) -> list[Filing]:
    """Point-in-time quarterly EPS versions from periodic filings.

    * a 10-Q's own three-month EPS is the original value of its fiscal quarter;
    * a 10-K's fiscal Q4 is derived as annual EPS minus Q1-Q3 known at acceptance;
    * three-month comparatives in later filings are new versions when they differ
      (restatements) or when the period was unknown before (e.g. pre-IPO quarters).
    """
    sid = f"CIK{cik:010d}"
    facts_by_acc: dict[str, list[EpsFact]] = {}
    for fact in facts:
        facts_by_acc.setdefault(fact.accession, []).append(fact)
    known = _Known()
    out: list[Filing] = []

    def add(label: str, end: date, value: float, meta: FilingMeta, comparative: bool) -> None:
        value = round(value, 4)
        previous = known.value.get(label)
        if previous is not None and abs(previous - value) < 0.005:
            return
        accession = meta.accession if not comparative else f"{meta.accession}#{label}"
        form = meta.form if not comparative else f"{meta.form} comparative"
        amends = known.original.get(label) if previous is not None else None
        if previous is None:
            known.original[label] = accession
        known.value[label] = value
        known.label_by_end[end] = label
        out.append(
            Filing(accession=accession, security_id=sid, form=form, fiscal_period=label, period_end=end,
                   filed_date=meta.filing_date, accepted_at=meta.accepted_at, eps=value, amends=amends)
        )

    for meta in filings:
        if meta.form not in PERIODIC or meta.report_date is None or meta.report_date < HISTORY_START:
            continue
        own = facts_by_acc.get(meta.accession, [])
        current = [f for f in own if f.end == meta.report_date]
        quarter = next((f for f in current if f.days is not None and 80 <= f.days <= 100), None)
        annual = next((f for f in current if f.days is not None and 350 <= f.days <= 380), None)
        q = _quarter_number((quarter or annual).fp) if (quarter or annual) else None
        fy = (quarter or annual).fy if (quarter or annual) else None
        if meta.form.startswith("10-Q") and quarter is not None and q in (1, 2, 3) and fy:
            add(f"{fy}Q{q}", quarter.end, quarter.value, meta, comparative=False)
        elif meta.form.startswith("10-K") and annual is not None and fy:
            parts = [known.value.get(f"{fy}Q{n}") for n in (1, 2, 3)]
            if all(p is not None for p in parts):
                add(f"{fy}Q4", annual.end, annual.value - sum(parts), meta, comparative=False)  # type: ignore[arg-type]
        # Three-month comparatives for earlier quarters reported in this filing.
        for fact in own:
            if fact.end == meta.report_date or fact.days is None or not 80 <= fact.days <= 100:
                continue
            label = known.label_by_end.get(fact.end)
            if label is None and quarter is not None and fy and q:
                if abs((meta.report_date - fact.end).days - 365) <= 10:  # same quarter, prior year
                    label = f"{fy - 1}Q{q}"
            if label is not None:
                add(label, fact.end, fact.value, meta, comparative=True)
    return out


def build_universe(client: EdgarClient, members: tuple[Member, ...] = UNIVERSE) -> dict[str, Any]:
    securities: list[dict[str, Any]] = []
    filings: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
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
        extracted = extract_filings(m.cik, metas, parse_eps_facts(facts_doc.json()))
        sid = f"CIK{m.cik:010d}"
        tickers = []
        for ticker, start, end in m.tickers:
            t_start = date.fromisoformat(start) if start else listed_from
            t_end = date.fromisoformat(end) if end else listed_to
            tickers.append({"ticker": ticker, "start": t_start.isoformat(), "end": t_end.isoformat() if t_end else None})
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
                "accession": f.accession, "security_id": f.security_id, "form": f.form,
                "fiscal_period": f.fiscal_period, "period_end": f.period_end.isoformat(),
                "filed_date": f.filed_date.isoformat(), "accepted_at": f.accepted_at.isoformat(),
                "eps": f.eps, "amends": f.amends,
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
        "notes": [
            "EPS is the XBRL basic EPS (falling back to diluted) for three-month periods.",
            "Fiscal Q4 EPS is derived as annual EPS minus Q1-Q3 as known when the 10-K was accepted.",
            "Comparative three-month values in later filings are recorded as new versions when they differ.",
            "Tickers are curated; EDGAR reports only current tickers.",
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
                TickerInterval(t["ticker"], date.fromisoformat(t["start"]), date.fromisoformat(t["end"]) if t["end"] else None)
                for t in s["tickers"]
            ),
        )
        for s in doc["securities"]
    )
    return secs, tuple(filing_from_dict(f) for f in doc["filings"])
