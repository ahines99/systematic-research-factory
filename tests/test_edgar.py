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
    EdgarClient,
    RateLimiter,
    check_source_uri,
    parse_acceptance,
    parse_eps_facts,
    parse_submissions,
)
from research_factory.data.edgar_universe import Member, extract_filings, listing_window, read_snapshot
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


def test_listing_window_uses_delisting_notice() -> None:
    metas, _ = _parsed()
    listed_from, listed_to, how = listing_window(
        metas, Member(98246, "TIFFANY", (("TIF", None, None),), "acquired")
    )
    notice = min(m.filing_date for m in metas if m.form == "25-NSE")
    assert listed_from == date(2019, 1, 2)
    assert listed_to is not None and listed_to < notice and "Form 25" in how


def test_extracted_filings_are_point_in_time_versions() -> None:
    metas, facts = _parsed()
    filings = extract_filings(98246, metas, facts)
    accepted = {m.accession: m.accepted_at for m in metas}
    assert filings
    for f in filings:
        assert (
            f.accepted_at == accepted[f.accession.split("#")[0]]
        )  # knowledge time = the filing's acceptance
        assert f.accepted_at.date() >= f.period_end
    periods = {f.fiscal_period for f in filings}
    assert any(p.endswith("Q4") for p in periods)  # derived from the 10-K
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
