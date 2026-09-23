"""Point-in-time views over filings: which version of which fiscal period was known when."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime

from .world import Filing, fiscal_period_minus

EPS_FLOOR = 0.25  # denominator floor so tiny prior-year EPS does not explode the ratio


def yoy_change(current_eps: float, prior_eps: float) -> float:
    """Year-over-year EPS change scaled by the prior-year level."""
    return (current_eps - prior_eps) / max(abs(prior_eps), EPS_FLOOR)


class FilingIndex:
    """Versions of each (security, fiscal period), ordered by acceptance time."""

    def __init__(self, filings: Iterable[Filing]):
        versions: dict[tuple[str, str], list[Filing]] = defaultdict(list)
        periods: dict[str, dict[str, date]] = defaultdict(dict)
        for f in filings:
            versions[(f.security_id, f.fiscal_period)].append(f)
            periods[f.security_id][f.fiscal_period] = f.period_end
        self._versions = {
            k: sorted(v, key=lambda f: (f.accepted_at, f.accession)) for k, v in versions.items()
        }
        self._accept_keys = {k: [f.accepted_at for f in v] for k, v in self._versions.items()}
        # For each security: periods sorted by period end.
        self._periods = {sid: sorted(p.items(), key=lambda item: item[1]) for sid, p in periods.items()}
        # For each security: originals sorted by acceptance, for "latest known period" lookups.
        originals: dict[str, list[Filing]] = defaultdict(list)
        for (sid, _), v in self._versions.items():
            originals[sid].extend(f for f in v if not f.is_amendment)
        self._originals = {
            sid: sorted(v, key=lambda f: (f.accepted_at, f.accession)) for sid, v in originals.items()
        }
        self._original_keys = {sid: [f.accepted_at for f in v] for sid, v in self._originals.items()}
        self.by_accession = {f.accession: f for v in self._versions.values() for f in v}

    def version_known_at(self, security_id: str, fiscal_period: str, ts: datetime) -> Filing | None:
        """Latest version of the period accepted at or before ``ts``."""
        key = (security_id, fiscal_period)
        versions = self._versions.get(key)
        if not versions:
            return None
        i = bisect_right(self._accept_keys[key], ts)
        return versions[i - 1] if i else None

    def final_version(self, security_id: str, fiscal_period: str) -> Filing | None:
        versions = self._versions.get((security_id, fiscal_period))
        return versions[-1] if versions else None

    def original(self, security_id: str, fiscal_period: str) -> Filing | None:
        versions = self._versions.get((security_id, fiscal_period))
        if not versions:
            return None
        originals = [f for f in versions if not f.is_amendment]
        return originals[0] if originals else versions[0]

    def latest_original_known_at(self, security_id: str, ts: datetime) -> Filing | None:
        """The most recently accepted original filing at or before ``ts``."""
        originals = self._originals.get(security_id)
        if not originals:
            return None
        i = bisect_right(self._original_keys[security_id], ts)
        if not i:
            return None
        # Latest by period end among those accepted, in case of out-of-order filings.
        return max(originals[:i], key=lambda f: (f.period_end, f.accepted_at))

    def latest_original_by_period_end(self, security_id: str, day: date) -> Filing | None:
        """The original filing with the latest period end on or before ``day`` (ignores acceptance)."""
        best: Filing | None = None
        for period, end in self._periods.get(security_id, []):
            if end > day:
                break
            candidate = self.original(security_id, period)
            if candidate is not None:
                best = candidate
        return best

    @staticmethod
    def year_ago(period: str) -> str:
        return fiscal_period_minus(period, 4)
