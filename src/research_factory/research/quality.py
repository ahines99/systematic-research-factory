"""Data-quality checks (RSF-058) and untrusted-text scanning.

Blocking problems (duplicates, impossible timestamps, non-positive prices, gaps while
listed) mean the data cannot support a conclusion: the run pauses with NEEDS_EVIDENCE.
Warnings (stale prices, extreme moves, instruction-like text) become findings.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..data.calendar import EASTERN
from ..data.world import MarketDataset

STALE_SESSIONS = 10
EXTREME_RETURN = 0.8
MAX_EXAMPLES = 5

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
        r"disregard (the )?(system|previous|above)",
        r"you are now",
        r"\bapprove (this|the) (strategy|run|hypothesis)\b",
        r"\b(system|assistant)\s*:",
        r"</?(system|instructions?)>",
        r"override (the )?(policy|policies|gate|rules)",
    )
]


@dataclass
class QualityIssue:
    check: str
    blocking: bool
    count: int
    statement: str
    examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "blocking": self.blocking,
            "count": self.count,
            "statement": self.statement,
            "examples": self.examples,
        }


def scan_untrusted_text(text: str) -> list[str]:
    """Return the instruction-like patterns found in ``text`` (data, never instructions)."""
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


def check_dataset(ds: MarketDataset) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    dupes = [acc for acc, n in Counter(f.accession for f in ds.filings).items() if n > 1]
    if dupes:
        issues.append(
            QualityIssue(
                "duplicate_filings",
                True,
                len(dupes),
                f"{len(dupes)} duplicate accession numbers.",
                [{"accession": a} for a in dupes[:MAX_EXAMPLES]],
            )
        )

    impossible = [f for f in ds.filings if f.accepted_at.astimezone(EASTERN).date() < f.period_end]
    if impossible:
        issues.append(
            QualityIssue(
                "accepted_before_period_end",
                True,
                len(impossible),
                f"{len(impossible)} filings were accepted before their fiscal period ended.",
                [
                    {"accession": f.accession, "period_end": f.period_end.isoformat()}
                    for f in impossible[:MAX_EXAMPLES]
                ],
            )
        )

    listed = ds.listed_mask
    closes = ds.raw_close
    gaps = listed & np.isnan(closes)
    if gaps.any():
        t_idx, i_idx = np.nonzero(gaps)
        issues.append(
            QualityIssue(
                "price_gaps",
                True,
                int(gaps.sum()),
                f"{int(gaps.sum())} missing closes for listed securities.",
                [
                    {"security_id": ds.security_ids[i], "session": ds.day(t).isoformat()}
                    for t, i in zip(t_idx[:MAX_EXAMPLES], i_idx[:MAX_EXAMPLES], strict=False)
                ],
            )
        )
    with np.errstate(invalid="ignore"):
        bad = listed & (closes <= 0)
    if bad.any():
        issues.append(
            QualityIssue(
                "non_positive_prices", True, int(bad.sum()), f"{int(bad.sum())} non-positive closes."
            )
        )

    stale = 0
    stale_examples: list[dict[str, Any]] = []
    for i, sid in enumerate(ds.security_ids):
        col = closes[:, i]
        run = 0
        for t in range(1, len(col)):
            same = listed[t, i] and listed[t - 1, i] and col[t] == col[t - 1]
            run = run + 1 if same else 0
            if run == STALE_SESSIONS:
                stale += 1
                if len(stale_examples) < MAX_EXAMPLES:
                    stale_examples.append({"security_id": sid, "session": ds.day(t).isoformat()})
    if stale:
        issues.append(
            QualityIssue(
                "stale_prices",
                False,
                stale,
                f"{stale} runs of {STALE_SESSIONS}+ unchanged closes.",
                stale_examples,
            )
        )

    r = ds.adjusted_returns
    with np.errstate(invalid="ignore"):
        extreme = np.abs(r) > EXTREME_RETURN
    if extreme.any():
        issues.append(
            QualityIssue(
                "extreme_returns",
                False,
                int(extreme.sum()),
                f"{int(extreme.sum())} daily moves above {EXTREME_RETURN:.0%}.",
            )
        )

    flagged = [(s.security_id, scan_untrusted_text(s.name)) for s in ds.securities]
    flagged = [(sid, pats) for sid, pats in flagged if pats]
    if flagged:
        issues.append(
            QualityIssue(
                "instruction_like_text",
                False,
                len(flagged),
                f"{len(flagged)} security names contain instruction-like text; it is treated as data only.",
                [{"security_id": sid, "patterns": pats} for sid, pats in flagged[:MAX_EXAMPLES]],
            )
        )
    return issues


def corrupt(ds: MarketDataset) -> MarketDataset:
    """Simulate a malformed upstream response: gaps and a duplicated filing."""
    from dataclasses import replace

    closes = ds.raw_close.copy()
    mid = len(closes) // 2
    listed = int(np.flatnonzero(ds.listed_mask[mid : mid + 3].all(axis=0))[0])
    closes[mid : mid + 3, listed] = np.nan
    return replace(ds, raw_close=closes, filings=(*ds.filings, ds.filings[0]))
