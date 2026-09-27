"""Model-spend budgets (RSF-071, ADR-0006).

Before every model call: per-run token and cost budgets and the global daily cost cap are
checked. Exceeding any of them raises ``BudgetExceededError``; the workflow pauses the run
(NEEDS_REVIEW, reason BUDGET_EXCEEDED) instead of spending more.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, time
from typing import Any

from sqlalchemy import Engine

from ..config import Budgets
from ..domain.clock import Clock
from ..domain.errors import BudgetExceededError
from ..judgment.providers import (
    PRICING,
    AnthropicProvider,
    JudgmentProvider,
    JudgmentRequest,
    JudgmentResponse,
    RulesProvider,
    ScriptedProvider,
)
from ..persistence.budget import BudgetReservations
from ..persistence.repositories import RunRepository, UsageRepository

GUEST = "guest"


def start_of_day(ts: datetime) -> datetime:
    return datetime.combine(ts.date(), time(0, 0), tzinfo=ts.tzinfo)


class BudgetGuard:
    def __init__(
        self,
        budgets: Budgets,
        usage: UsageRepository,
        runs: RunRepository,
        clock: Clock,
        *,
        accounting_engine: Engine | None = None,
    ):
        self.budgets = budgets
        self.usage = usage
        self.runs = runs
        self.clock = clock
        # Evaluation cases may isolate research state while sharing the durable
        # owner's spend ledger. None preserves ordinary service-local accounting.
        self.accounting_engine = accounting_engine

    def invoke(
        self, provider: JudgmentProvider, request: JudgmentRequest, run_id: str, step: str, engine: Any
    ) -> JudgmentResponse:
        """Reserve, dispatch and settle inside the worker, even if its waiter times out.

        An ambiguous transport failure retains its reservation. Explicit operator
        reconciliation is required before retrying that step; no guessed refunds.
        """
        reservations = BudgetReservations(
            self.accounting_engine if self.accounting_engine is not None else engine
        )
        offline = type(provider) in (RulesProvider, ScriptedProvider)
        if type(provider) is RulesProvider:
            input_bound, output_bound = 0, 0
        elif type(provider) is ScriptedProvider:
            input_bound, output_bound = 1000, 200
        else:
            # A byte is a conservative upper bound on text tokens; the allowance
            # covers message/schema framing. Include feedback and full skill text.
            encoded = json.dumps(
                {
                    "system": request.system,
                    "payload": request.payload,
                    "schema": request.schema,
                    "feedback": request.feedback,
                },
                ensure_ascii=False,
            )
            input_bound = len(encoded.encode("utf-8")) + 8192
            output_bound = request.max_output_tokens
            if provider.name == "anthropic" and provider.model not in PRICING:
                raise BudgetExceededError("unknown model price; configure a reviewed price before dispatch")
            if isinstance(provider, AnthropicProvider):
                counted = provider.input_token_bound(request)
                if counted is not None:
                    input_bound = counted
        input_rate, output_rate = (
            (0.0, 0.0)
            if offline
            else (max(p[0] for p in PRICING.values()), max(p[1] for p in PRICING.values()))
        )
        now = self.clock.now()
        call_id, output_limit = reservations.reserve(
            budgets=self.budgets,
            run_id=run_id,
            step=step,
            model=provider.model,
            input_tokens=input_bound,
            max_output_tokens=output_bound,
            input_rate=input_rate,
            output_rate=output_rate,
            now=now,
            day=start_of_day(now),
        )
        try:
            response = provider.judge(replace(request, max_output_tokens=output_limit))
        except Exception:
            if offline:
                reservations.settle(
                    call_id,
                    now=self.clock.now(),
                    model=provider.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                )
            else:
                reservations.uncertain(call_id)
            raise
        reservations.settle(
            call_id,
            now=self.clock.now(),
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
        )
        if response.error is not None:
            raise response.error
        return response

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
