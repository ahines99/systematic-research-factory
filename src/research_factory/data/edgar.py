"""SEC EDGAR adapter (RSF-055).

* ``submissions``: filing metadata. ``acceptanceDateTime`` is the knowledge time. It is UTC
  (verified 2026-09-23 against 3,005 filings: label hours span 10:00-02:00, i.e. EDGAR's
  06:00-22:00 Eastern acceptance window, and next-day filing dates begin at 21:30Z).
* ``companyfacts``: XBRL facts. A fact's ``filed`` field is a date only, so each fact is
  joined to its filing's acceptance time through the accession number.

Fair access: every request declares a User-Agent (``RSF_SEC_USER_AGENT``, which should name
an organization and a contact address) and requests stay under SEC's 10-per-second limit.
Responses are cached on disk by URL, and every body is content-hashed.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..domain.errors import DomainError, ErrorCode, ForbiddenError, NotFoundError, UpstreamUnavailableError
from ..domain.identity import sha256_hex

BASE = "https://data.sec.gov"
EPS_CONCEPTS = ("EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted", "EarningsPerShareDiluted")


def check_source_uri(uri: str, allowed_hosts: tuple[str, ...]) -> None:
    """SSRF guard: only HTTPS URLs on allowlisted hosts may be fetched."""
    parsed = urlparse(uri)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.port not in (None, 443):
        raise ForbiddenError(f"fetching {uri!r} is not allowed")


class RateLimiter:
    def __init__(self, per_second: float, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.interval = 1.0 / per_second
        self.clock = clock
        self.sleep = sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self.clock()
            if now < self._next:
                self.sleep(self._next - now)
                now = self._next
            self._next = now + self.interval


@dataclass(frozen=True)
class FetchResult:
    url: str
    body: bytes
    content_hash: str
    from_cache: bool

    def json(self) -> Any:
        return json.loads(self.body)


class EdgarClient:
    def __init__(
        self,
        user_agent: str | None,
        cache_dir: Path | None = None,
        requests_per_second: float = 5.0,
        http: httpx.Client | None = None,
        allowed_hosts: tuple[str, ...] = ("data.sec.gov", "www.sec.gov"),
        limiter: RateLimiter | None = None,
    ):
        if not user_agent or not user_agent.strip():
            raise DomainError(
                "SEC requires a declared User-Agent; set RSF_SEC_USER_AGENT to '<organization> <contact email>'",
                code=ErrorCode.INVALID_INPUT,
            )
        if requests_per_second > 10:
            raise DomainError("SEC fair access allows at most 10 requests per second", code=ErrorCode.INVALID_INPUT)
        self.user_agent = user_agent
        self.cache_dir = cache_dir
        self.allowed_hosts = allowed_hosts
        self.limiter = limiter or RateLimiter(requests_per_second)
        self.http = http or httpx.Client(timeout=30.0, headers={"Accept-Encoding": "gzip, deflate"})

    def _cache_path(self, url: str) -> Path | None:
        return self.cache_dir / f"{sha256_hex(url.encode())[:32]}.json" if self.cache_dir else None

    def fetch(self, url: str, *, use_cache: bool = True) -> FetchResult:
        check_source_uri(url, self.allowed_hosts)
        path = self._cache_path(url)
        if use_cache and path is not None and path.exists():
            body = path.read_bytes()
            return FetchResult(url, body, sha256_hex(body), True)
        self.limiter.wait()
        try:
            response = self.http.get(url, headers={"User-Agent": self.user_agent})
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError(f"EDGAR request failed: {type(exc).__name__}") from exc
        if response.status_code == 404:
            raise NotFoundError(f"EDGAR has no resource at {url}")
        if response.status_code in (403, 429) or response.status_code >= 500:
            raise UpstreamUnavailableError(f"EDGAR returned {response.status_code} for {url}")
        if response.status_code != 200:
            raise DomainError(f"EDGAR returned {response.status_code}", code=ErrorCode.INVALID_INPUT)
        body = response.content
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        return FetchResult(url, body, sha256_hex(body), False)

    def submissions(self, cik: str) -> list[FetchResult]:
        """The main submissions document plus any older pages it references."""
        first = self.fetch(f"{BASE}/submissions/CIK{int(cik):010d}.json")
        pages = [first]
        for extra in first.json().get("filings", {}).get("files", []):
            pages.append(self.fetch(f"{BASE}/submissions/{extra['name']}"))
        return pages

    def companyfacts(self, cik: str) -> FetchResult:
        return self.fetch(f"{BASE}/api/xbrl/companyfacts/CIK{int(cik):010d}.json")


# --------------------------------------------------------------------------- parsing


@dataclass(frozen=True)
class FilingMeta:
    accession: str
    form: str
    filing_date: date
    report_date: date | None
    accepted_at: datetime


def parse_acceptance(text: str) -> datetime:
    """``2023-11-02T22:04:43.000Z`` -> aware UTC datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)


def parse_submissions(pages: list[dict[str, Any]]) -> list[FilingMeta]:
    out: dict[str, FilingMeta] = {}
    for i, page in enumerate(pages):
        cols = page["filings"]["recent"] if i == 0 else page
        for j, accession in enumerate(cols["accessionNumber"]):
            report = cols["reportDate"][j]
            out[accession] = FilingMeta(
                accession=accession,
                form=cols["form"][j],
                filing_date=date.fromisoformat(cols["filingDate"][j]),
                report_date=date.fromisoformat(report) if report else None,
                accepted_at=parse_acceptance(cols["acceptanceDateTime"][j]),
            )
    return sorted(out.values(), key=lambda f: (f.accepted_at, f.accession))


@dataclass(frozen=True)
class EpsFact:
    accession: str
    start: date | None
    end: date
    value: float
    fy: int | None
    fp: str | None
    form: str

    @property
    def days(self) -> int | None:
        return (self.end - self.start).days if self.start else None


def parse_eps_facts(companyfacts: dict[str, Any]) -> list[EpsFact]:
    """EPS facts merged across concepts; for the same filing and period, basic EPS wins."""
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    merged: dict[tuple[str, str | None, str], EpsFact] = {}
    for concept in reversed(EPS_CONCEPTS):  # later (preferred) concepts overwrite earlier ones
        for r in gaap.get(concept, {}).get("units", {}).get("USD/shares", []):
            fact = EpsFact(
                accession=r["accn"],
                start=date.fromisoformat(r["start"]) if r.get("start") else None,
                end=date.fromisoformat(r["end"]),
                value=float(r["val"]),
                fy=r.get("fy"),
                fp=r.get("fp"),
                form=r.get("form", ""),
            )
            merged[(fact.accession, r.get("start"), r["end"])] = fact
    return sorted(merged.values(), key=lambda f: (f.accession, f.end, f.start or f.end))
