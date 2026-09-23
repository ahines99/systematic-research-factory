"""Model-spend budgets (RSF-071, ADR-0006).

Before every model call: per-run token and cost budgets and the global daily cost cap are
checked. Exceeding any of them raises ``BudgetExceededError``; the workflow pauses the run
(NEEDS_REVIEW, reason BUDGET_EXCEEDED) instead of spending more.
"""

from __future__ import annotations

from datetime import datetime, time

from ..config import Budgets
from ..domain.clock import Clock
from ..domain.errors import BudgetExceededError
from ..persistence.repositories import RunRepository, UsageRepository

GUEST = "guest"


def start_of_day(ts: datetime) -> datetime:
    return datetime.combine(ts.date(), time(0, 0), tzinfo=ts.tzinfo)


class BudgetGuard:
    def __init__(self, budgets: Budgets, usage: UsageRepository, runs: RunRepository, clock: Clock):
        self.budgets = budgets
        self.usage = usage
        self.runs = runs
        self.clock = clock

    def check(self, run_id: str | None) -> None:
        if run_id is not None:
            tokens, cost = self.usage.totals_for_run(run_id)
            if tokens >= self.budgets.max_tokens_per_run:
                raise BudgetExceededError(
                    f"run token budget reached ({tokens} >= {self.budgets.max_tokens_per_run})"
                )
            if cost >= self.budgets.max_cost_usd_per_run:
                raise BudgetExceededError(
                    f"run cost budget reached (${cost:.2f} >= ${self.budgets.max_cost_usd_per_run:.2f})"
                )
        spent = self.usage.cost_since(start_of_day(self.clock.now()))
        if spent >= self.budgets.max_cost_usd_per_day:
            raise BudgetExceededError(
                f"daily model-spend cap reached (${spent:.2f} >= ${self.budgets.max_cost_usd_per_day:.2f}); live runs resume tomorrow"
            )

    def record(
        self,
        *,
        run_id: str | None,
        step: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        self.usage.add(
            run_id=run_id,
            step=step,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            created_at=self.clock.now(),
        )

    def spent_today(self) -> float:
        return self.usage.cost_since(start_of_day(self.clock.now()))

    def guest_runs_remaining(self) -> int:
        used = self.runs.count_created_since(GUEST, start_of_day(self.clock.now()))
        return max(0, self.budgets.max_guest_live_runs_per_day - used)

    def check_guest_run(self) -> None:
        if self.guest_runs_remaining() <= 0:
            raise BudgetExceededError(
                "the daily limit of guest live runs has been reached; browse the recorded runs instead"
            )
        self.check(None)
