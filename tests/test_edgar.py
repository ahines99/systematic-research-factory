"""RSF-055 to RSF-059: EDGAR adapter, security master, semi-synthetic prices, snapshots.

Contract tests run against recorded (trimmed) SEC responses for Tiffany & Co., which was
acquired inside the sample window. No network access is needed.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from research_factory.data.edgar import (
    NET_INCOME_CONCEPTS,
    SHARE_CONCEPTS,
    EdgarClient,
    EpsFact,
    FilingMeta,
    RateLimiter,
    check_source_uri,
    parse_acceptance,
    parse_concept_facts,
    parse_eps_facts,
    parse_submissions,
)
from research_factory.data.edgar_universe import (
    Member,
    classify_revision,
    extract_filings,
    extract_with_report,
    listing_window,
    period_label,
    read_snapshot,
)
from research_factory.data.fundamentals import FilingIndex
from research_factory.data.pit import PointInTimeData
from research_factory.data.registry import get_dataset
from research_factory.data.semi_synthetic import SNAPSHOT, load_edgar_semi_synthetic
from research_factory.domain.errors import (
    DomainError,
    ForbiddenError,
    NotFoundError,
    UpstreamUnavailableError,
)

FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
UA = "SystematicResearchFactory/0.1 tests"


def _transport(status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == UA
        name = request.url.path.rsplit("/", 1)[-1]
        prefix = "companyfacts_" if "companyfacts" in request.url.path else "submissions_"
        path = FIXTURES / f"{prefix}{name}"
        if status != 200:
            return httpx.Response(status)
        if not path.exists():
            return httpx.Response(404)
        return httpx.Response(200, content=path.read_bytes())

    return httpx.MockTransport(handler)


def _client(tmp_path: Path | None = None, status: int = 200) -> EdgarClient:
    return EdgarClient(
        UA,
        cache_dir=tmp_path,
        http=httpx.Client(transport=_transport(status)),
        limiter=RateLimiter(1000, sleep=lambda s: None),
    )


def test_user_agent_and_rate_limit_are_required() -> None:
    with pytest.raises(DomainError, match="User-Agent"):
        EdgarClient(None)
    with pytest.raises(DomainError, match="10 requests"):
        EdgarClient(UA, requests_per_second=20)


def test_ssrf_allowlist() -> None:
    check_source_uri("https://data.sec.gov/submissions/CIK1.json", ("data.sec.gov",))
    for bad in (
        "http://data.sec.gov/x",
        "https://evil.example/x",
        "https://data.sec.gov.evil.example/x",
        "https://user@data.sec.gov/x",
        "https://data.sec.gov:8443/x",
        "file:///etc/passwd",
    ):
        with pytest.raises(ForbiddenError):
            check_source_uri(bad, ("data.sec.gov",))


def test_rate_limiter_spaces_requests() -> None:
    now = [0.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        now[0] += s

    limiter = RateLimiter(5, clock=lambda: now[0], sleep=sleep)
    for _ in range(3):
        limiter.wait()
    assert slept == pytest.approx([0.2, 0.2])


def test_fetch_caches_and_hashes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = client.companyfacts("98246")
    second = client.companyfacts("98246")
    assert not first.from_cache and second.from_cache
    assert first.content_hash == second.content_hash and len(first.content_hash) == 64


@pytest.mark.parametrize(
    ("status", "error"),
    [(404, NotFoundError), (429, UpstreamUnavailableError), (503, UpstreamUnavailableError)],
)
def test_http_errors_are_typed(status: int, error: type[Exception]) -> None:
    with pytest.raises(error):
        _client(status=status).companyfacts("98246")


def test_acceptance_times_are_utc() -> None:
    ts = parse_acceptance("2020-11-24T11:02:33.000Z")
    assert ts == datetime(2020, 11, 24, 11, 2, 33, tzinfo=UTC)


def _parsed() -> tuple[list, list]:  # type: ignore[type-arg]
    client = _client()
    metas = parse_submissions([p.json() for p in client.submissions("98246")])
    facts = parse_eps_facts(client.companyfacts("98246").json())
    return metas, facts


def _parsed_all() -> tuple[list, list, list, list]:  # type: ignore[type-arg]
    client = _client()
    metas = parse_submissions([p.json() for p in client.submissions("98246")])
    doc = client.companyfacts("98246").json()
    return (
        metas,
        parse_eps_facts(doc),
        parse_concept_facts(doc, NET_INCOME_CONCEPTS, "USD"),
        parse_concept_facts(doc, SHARE_CONCEPTS, "shares"),
    )


def test_listing_window_uses_delisting_notice() -> None:
    metas, _ = _parsed()
    listed_from, listed_to, how = listing_window(
        metas, Member(98246, "TIFFANY", (("TIF", None, None),), "acquired")
    )
    notice = min(m.filing_date for m in metas if m.form == "25-NSE")
    assert listed_from == date(2019, 1, 2)
    assert listed_to is not None and listed_to < notice and "Form 25" in how


def test_extracted_filings_are_point_in_time_versions() -> None:
    metas, facts, net_income, shares = _parsed_all()
    filings, report = extract_with_report(98246, metas, facts, net_income, shares)
    assert report.counts.get("q4_from_net_income", 0) + report.counts.get("q4_reported", 0) >= 2
    accepted = {m.accession: m.accepted_at for m in metas}
    assert filings
    for f in filings:
        assert (
            f.accepted_at == accepted[f.accession.split("#")[0]]
        )  # knowledge time = the filing's acceptance
        assert f.accepted_at.date() >= f.period_end
    q4 = [f for f in filings if f.form.startswith("10-K") and f.revision == "original"]
    assert q4 and all(0 < f.eps < 3 for f in q4)  # Tiffany's fiscal Q4 EPS was roughly $1-2
    idx = FilingIndex(filings)
    for f in filings:
        if f.amends:
            assert idx.by_accession[f.amends].fiscal_period == f.fiscal_period


def test_snapshot_is_committed_and_consistent() -> None:
    doc = read_snapshot(SNAPSHOT)
    assert doc["format"] == "rsf-edgar-universe/1"
    assert len(doc["securities"]) == 44 and len(doc["provenance"]) >= 88
    exits = [s for s in doc["securities"] if s["listed_to"]]
    assert len(exits) >= 10
    ids = {s["security_id"] for s in doc["securities"]}
    assert all(f["security_id"] in ids for f in doc["filings"])
    assert all(len(p["sha256"]) == 64 for p in doc["provenance"])


def test_meta_ticker_history() -> None:
    ds = get_dataset("edgar-semi:v1")
    pit = PointInTimeData(ds)
    assert pit.resolve_ticker("FB", datetime(2021, 6, 1, 23, tzinfo=UTC)).security_id == "CIK0001326801"  # type: ignore[union-attr]
    assert pit.resolve_ticker("FB", datetime(2023, 6, 1, 23, tzinfo=UTC)) is None
    assert pit.resolve_ticker("META", datetime(2023, 6, 1, 23, tzinfo=UTC)).security_id == "CIK0001326801"  # type: ignore[union-attr]


def test_semi_synthetic_prices_are_labelled_and_reproducible() -> None:
    a, b = load_edgar_semi_synthetic(), load_edgar_semi_synthetic()
    assert a.prices_simulated and a.content_hash == b.content_hash
    assert a.planted["knowledge_basis"] == "acceptance" and a.planted["n_events"] > 500
    assert set(a.planted["delisted"]) and set(a.planted["ipos"])


def test_recorded_fixture_is_trimmed_real_data() -> None:
    doc = json.loads((FIXTURES / "submissions_CIK0000098246.json").read_text())
    assert doc["name"].upper().startswith("TIFFANY")


def test_period_labels_are_stable_across_52_53_week_years() -> None:
    assert period_label(date(2022, 1, 2)) == "P2021-12"
    assert period_label(date(2021, 1, 3)) == "P2020-12"
    assert period_label(date(2020, 9, 26)) == "P2020-09"
    assert period_label(date(2016, 9, 3)) == "P2016-08" and period_label(date(2017, 9, 9)) == "P2017-08"


def test_revision_classification() -> None:
    assert classify_revision(1.00, 1.004) is None  # rounding
    assert classify_revision(27.69, 1.3845) == "split_adjusted"  # 20-for-1
    assert classify_revision(0.50, 1.00) == "split_adjusted"  # reverse split
    assert classify_revision(1.00, 1.20) == "restated"


def _meta(acc: str, form: str, report: date, accepted_day: date) -> FilingMeta:
    return FilingMeta(
        acc, form, accepted_day, report, datetime.combine(accepted_day, datetime.min.time(), tzinfo=UTC)
    )


def _fact(acc: str, start: date, end: date, value: float) -> EpsFact:
    return EpsFact(acc, start, end, value, None, None, "")


def test_q4_from_net_income_survives_a_mid_year_split() -> None:
    """Audit Q2: a 4-for-1 split after Q1 made 'annual EPS minus Q1-Q3' nonsense."""
    y0, q1, q2, q3, fy = (
        date(2019, 12, 31),
        date(2020, 3, 31),
        date(2020, 6, 30),
        date(2020, 9, 30),
        date(2020, 12, 31),
    )
    metas = [
        _meta("q1", "10-Q", q1, date(2020, 5, 1)),
        _meta("q2", "10-Q", q2, date(2020, 8, 1)),
        _meta("q3", "10-Q", q3, date(2020, 11, 1)),
        _meta("k", "10-K", fy, date(2021, 2, 1)),
    ]
    eps = [
        _fact("q1", y0, q1, 4.00),
        _fact("q2", q1, q2, 1.00),
        _fact("q3", q2, q3, 1.00),
        _fact("k", y0, fy, 4.00),
    ]
    ni = [
        _fact("q1", y0, q1, 100.0),
        _fact("q2", q1, q2, 100.0),
        _fact("q3", q2, q3, 100.0),
        _fact("k", y0, fy, 400.0),
    ]
    shares = [_fact("k", y0, fy, 100.0)]
    filings = extract_filings(1, metas, eps, ni, shares)
    q4 = next(f for f in filings if f.accession == "k")
    assert q4.eps == pytest.approx(1.00)  # EPS subtraction would give 4 - 6 = -2


def test_units_guard_rejects_shares_tagged_in_millions() -> None:
    y0, q1, q2, q3, fy = (
        date(2019, 12, 31),
        date(2020, 3, 31),
        date(2020, 6, 30),
        date(2020, 9, 30),
        date(2020, 12, 31),
    )
    metas = [
        _meta("q1", "10-Q", q1, date(2020, 5, 1)),
        _meta("q2", "10-Q", q2, date(2020, 8, 1)),
        _meta("q3", "10-Q", q3, date(2020, 11, 1)),
        _meta("k", "10-K", fy, date(2021, 2, 1)),
    ]
    eps = [
        _fact("q1", y0, q1, 2.0),
        _fact("q2", q1, q2, 2.0),
        _fact("q3", q2, q3, 2.0),
        _fact("k", y0, fy, 8.0),
    ]
    ni = [
        _fact("q1", y0, q1, 2e9),
        _fact("q2", q1, q2, 2e9),
        _fact("q3", q2, q3, 2e9),
        _fact("k", y0, fy, 8e9),
    ]
    shares = [_fact("k", y0, fy, 1000.0)]  # really 1,000 million
    filings, report = extract_with_report(1, metas, eps, ni, shares)
    q4 = next(f for f in filings if f.accession == "k")
    assert q4.eps == pytest.approx(2.0) and report.counts["q4_net_income_inconsistent"] == 1


def test_snapshot_q4_values_are_plausible() -> None:
    doc = read_snapshot(SNAPSHOT)
    by = {
        (f["security_id"], f["fiscal_period"]): f["eps"]
        for f in doc["filings"]
        if f["revision"] == "original"
    }
    assert by[("CIK0000320193", "P2020-09")] == pytest.approx(0.73, abs=0.03)  # Apple FY20 Q4, post-split
    assert by[("CIK0001018724", "P2022-12")] == pytest.approx(0.03, abs=0.02)  # Amazon 2022 Q4
    assert by[("CIK0001045810", "P2022-01")] == pytest.approx(1.18, abs=0.05)  # NVIDIA FY22 Q4
    assert by[("CIK0000063908", "P2022-12")] == pytest.approx(2.59, abs=0.05)  # McDonald's 2022 Q4
    assert max(f["accepted_at"] for f in doc["filings"]) < "2024-01-06"
    assert set(doc["extraction"]) >= {"q4_from_net_income", "split_adjusted", "restated"}
