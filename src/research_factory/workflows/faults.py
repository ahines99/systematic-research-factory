"""Failure injection (RSF-046): make dependencies fail on purpose, in tests and demos."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..domain.errors import StepTimeoutError, UpstreamUnavailableError


class FaultKind(StrEnum):
    TIMEOUT = "timeout"  # the dependency does not answer in time (transient)
    OUTAGE = "outage"  # the dependency is down (transient; persistent if times is large)
    MALFORMED = "malformed"  # the dependency answers with corrupt data


@dataclass
class FaultRule:
    target: str
    kind: FaultKind
    times: int = 1  # how many calls fail before the dependency recovers

    @classmethod
    def parse(cls, text: str) -> FaultRule:
        """``target:kind[:times]``, e.g. ``data_source:timeout:1``."""
        parts = text.split(":")
        if len(parts) not in (2, 3):
            raise ValueError("fault must be target:kind[:times]")
        return cls(parts[0], FaultKind(parts[1]), int(parts[2]) if len(parts) == 3 else 1)


class FaultInjector:
    def __init__(self, rules: list[FaultRule] | None = None):
        self.rules = list(rules or [])
        self.fired: list[tuple[str, str]] = []

    def _take(self, target: str, kinds: tuple[FaultKind, ...]) -> FaultRule | None:
        for rule in self.rules:
            if rule.target == target and rule.kind in kinds and rule.times > 0:
                rule.times -= 1
                self.fired.append((target, str(rule.kind)))
                return rule
        return None

    def check(self, target: str) -> None:
        """Raise a transient error if a timeout or outage is scheduled for ``target``."""
        rule = self._take(target, (FaultKind.TIMEOUT, FaultKind.OUTAGE))
        if rule is None:
            return
        if rule.kind is FaultKind.TIMEOUT:
            raise StepTimeoutError(f"injected timeout calling {target}")
        raise UpstreamUnavailableError(f"injected outage: {target} is unavailable")

    def should_corrupt(self, target: str) -> bool:
        return self._take(target, (FaultKind.MALFORMED,)) is not None


NO_FAULTS = FaultInjector()
