"""Leakage audit (RSF-020).

The audit trusts evidence, not the feature builder. For every lineage input it
re-derives the knowledge time from the stored evidence (filing acceptance times, session
closes) and compares it with the decision time. It also checks execution delay,
point-in-time universe membership, and whether the prediction target was used as a feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ..data.calendar import close_utc
from ..data.world import MarketDataset
from ..domain.models import Severity

MAX_EXAMPLES = 5


@dataclass
class AuditCheck:
    check: str
    passed: bool
    severity: Severity
    statement: str
    violations: int = 0
    examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "passed": self.passed,
            "severity": str(self.severity),
            "statement": self.statement,
            "violations": self.violations,
            "examples": self.examples,
        }


@dataclass
class LeakageReport:
    checks: list[AuditCheck]

    @property
    def blocking(self) -> bool:
        return any(not c.passed and c.severity is Severity.BLOCKING for c in self.checks)

    def to_document(self) -> dict[str, Any]:
        return {
            "format": "rsf-leakage-audit/1",
            "blocking": self.blocking,
            "checks": [c.to_dict() for c in self.checks],
        }


def _knowledge_time(locator: str, accepted: dict[str, datetime]) -> datetime | None:
    kind, _, rest = locator.partition(":")
    if kind == "filing":
        return accepted.get(rest)
    if kind == "price":
        _, _, day = rest.rpartition(":")
        try:
            return close_utc(date.fromisoformat(day))
        except ValueError:
            return None
    return None


def check_knowledge_times(lineage_rows: list[dict[str, Any]], accepted: dict[str, datetime]) -> AuditCheck:
    violations = 0
    unverifiable = 0
    misreported = 0
    examples: list[dict[str, Any]] = []
    for row in lineage_rows:
        decision = datetime.fromisoformat(row["decision_ts"])
        for inp in row["inputs"]:
            actual = _knowledge_time(inp["locator"], accepted)
            if actual is None:
                unverifiable += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append(
                        {
                            "security_id": row["security_id"],
                            "locator": inp["locator"],
                            "problem": "unverifiable",
                        }
                    )
                continue
            claimed = datetime.fromisoformat(inp["knowledge_ts"])
            if claimed != actual:
                misreported += 1
            if actual > decision:
                violations += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append(
                        {
                            "security_id": row["security_id"],
                            "decision_ts": row["decision_ts"],
                            "locator": inp["locator"],
                            "knowledge_ts": actual.isoformat(),
                            "days_ahead": round((actual - decision).total_seconds() / 86400, 2),
                        }
                    )
    total = violations + unverifiable
    if total == 0:
        statement = f"All {sum(len(r['inputs']) for r in lineage_rows)} feature inputs were knowable at decision time."
    else:
        statement = (
            f"{violations} feature inputs were not knowable at decision time"
            f"{f' and {unverifiable} could not be verified against evidence' if unverifiable else ''}."
        )
    if misreported:
        statement += f" {misreported} inputs reported a knowledge time that differs from the evidence."
    return AuditCheck("knowledge_time", total == 0, Severity.BLOCKING, statement, total, examples)


def check_execution_delay(backtest_doc: dict[str, Any]) -> AuditCheck:
    lag = int(backtest_doc["lag_sessions"])
    if lag >= 1:
        return AuditCheck(
            "execution_delay",
            True,
            Severity.BLOCKING,
            f"Trades execute {lag} session(s) after the decision close "
            f"(delay {backtest_doc['execution_delay_minutes']} minutes).",
        )
    return AuditCheck(
        "execution_delay",
        False,
        Severity.BLOCKING,
        "Trades execute at the same close the signal is computed from, which cannot be achieved in practice.",
        1,
    )


def check_universe(backtest_doc: dict[str, Any], dataset: MarketDataset) -> AuditCheck:
    """Every security listed on a decision date must have been eligible (no survivorship filter)."""
    violations = 0
    examples: list[dict[str, Any]] = []
    for entry in backtest_doc["universe_by_decision"]:
        day = date.fromisoformat(entry["decision"])
        used = set(entry["universe"])
        expected = {s.security_id for s in dataset.securities if s.is_listed(day)}
        missing = sorted(expected - used)
        extra = sorted(used - expected)
        if missing or extra:
            violations += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append(
                    {"decision": entry["decision"], "missing": missing[:10], "not_listed": extra[:10]}
                )
    if violations == 0:
        return AuditCheck(
            "universe",
            True,
            Severity.BLOCKING,
            "The universe matched point-in-time listings on every decision date.",
        )
    return AuditCheck(
        "universe",
        False,
        Severity.BLOCKING,
        f"On {violations} decision dates the universe differed from point-in-time listings "
        "(securities that were listed then were excluded, or unlisted ones included): survivorship bias.",
        violations,
        examples,
    )


def check_target(input_sources: frozenset[str], feature: str) -> AuditCheck:
    if "forward_return" in input_sources:
        return AuditCheck(
            "target_leakage",
            False,
            Severity.BLOCKING,
            f"Feature {feature!r} is built from forward returns, which is the prediction target.",
            1,
        )
    return AuditCheck(
        "target_leakage", True, Severity.BLOCKING, f"Feature {feature!r} does not use the prediction target."
    )


def audit_leakage(
    *,
    feature_doc: dict[str, Any],
    backtest_doc: dict[str, Any],
    filings_doc: list[dict[str, Any]],
    dataset: MarketDataset,
    input_sources: frozenset[str],
) -> LeakageReport:
    accepted = {f["accession"]: datetime.fromisoformat(f["accepted_at"]) for f in filings_doc}
    return LeakageReport(
        [
            check_knowledge_times(feature_doc["lineage"]["rows"], accepted),
            check_execution_delay(backtest_doc),
            check_universe(backtest_doc, dataset),
            check_target(input_sources, feature_doc["feature"]),
        ]
    )
