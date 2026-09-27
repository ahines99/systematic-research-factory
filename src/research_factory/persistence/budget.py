"""Transactional model-call reservations shared by every worker.

Uncertain calls never expire automatically: a timeout is not proof that a provider
stopped billing. The caller must reconcile them before the same step can retry.
"""

from __future__ import annotations

import math
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from weakref import WeakKeyDictionary

from sqlalchemy import Column, Float, Integer, String, Table, func, insert, select, update
from sqlalchemy.engine import Engine

from ..config import Budgets
from ..domain.errors import BudgetExceededError, InvalidInputError, NotFoundError
from ..domain.identity import canonical_json, sha256_hex
from . import schema as s

budget_lock = Table(
    "budget_lock",
    s.metadata,
    Column("lock_id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)
model_reservations = Table(
    "model_reservations",
    s.metadata,
    Column("reservation_id", String(64), primary_key=True),
    Column("run_id", String(64)),
    Column("step", String(64), nullable=False),
    Column("model", String(120), nullable=False),
    Column("tokens", Integer, nullable=False),
    Column("cost_usd", Float, nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", s.UTCDateTime, nullable=False),
)

_locks: WeakKeyDictionary[Engine, Any] = WeakKeyDictionary()
_registry_lock = threading.Lock()


class BudgetReservations:
    def __init__(self, engine: Engine):
        self.engine = engine
        with _registry_lock:
            self.local_lock = _locks.setdefault(engine, threading.RLock())

    @contextmanager
    def transaction(self) -> Any:
        # Also protects SQLite StaticPool's single connection in offline tests.
        # The database row lock, not this process-local mutex, coordinates workers.
        with self.local_lock, self.engine.begin() as conn:
            locked = conn.execute(
                update(budget_lock)
                .where(budget_lock.c.lock_id == 1)
                .values(version=budget_lock.c.version + 1)
            )
            if locked.rowcount != 1:
                raise BudgetExceededError("budget lock is unavailable; refusing model dispatch")
            yield conn

    def reserve(
        self,
        *,
        budgets: Budgets,
        run_id: str | None,
        step: str,
        model: str,
        input_tokens: int,
        max_output_tokens: int,
        input_rate: float,
        output_rate: float,
        now: datetime,
        day: datetime,
    ) -> tuple[str, int]:
        with self.transaction() as conn:
            pending = (
                conn.execute(
                    select(model_reservations).where(
                        model_reservations.c.status.in_(("pending", "uncertain"))
                    )
                )
                .mappings()
                .all()
            )
            if any(r["run_id"] == run_id and r["step"] == step for r in pending):
                raise BudgetExceededError(
                    "a previous model call for this step is still pending or uncertain; reconcile it before retrying"
                )
            used_tokens, used_cost = conn.execute(
                select(
                    func.coalesce(func.sum(s.model_usage.c.input_tokens + s.model_usage.c.output_tokens), 0),
                    func.coalesce(func.sum(s.model_usage.c.cost_usd), 0.0),
                ).where(s.model_usage.c.run_id == run_id)
            ).one()
            day_cost = conn.execute(
                select(func.coalesce(func.sum(s.model_usage.c.cost_usd), 0.0)).where(
                    s.model_usage.c.created_at >= day
                )
            ).scalar_one()
            run_pending = [r for r in pending if r["run_id"] == run_id]
            tokens_left = budgets.max_tokens_per_run - used_tokens - sum(r["tokens"] for r in run_pending)
            run_left = budgets.max_cost_usd_per_run - used_cost - sum(r["cost_usd"] for r in run_pending)
            day_left = budgets.max_cost_usd_per_day - day_cost - sum(r["cost_usd"] for r in pending)
            if day_left <= 0:
                raise BudgetExceededError("daily model-spend cap reached or reserved by outstanding calls")
            if run_left <= 0 or tokens_left <= 0:
                raise BudgetExceededError("run model budget reached or reserved by outstanding calls")
            allowance = min(max_output_tokens, tokens_left - input_tokens)
            if output_rate:
                allowance = min(
                    allowance,
                    math.floor(
                        (min(run_left, day_left) * 1_000_000 - input_tokens * input_rate) / output_rate
                    ),
                )
            if allowance < min(256, max_output_tokens):
                raise BudgetExceededError("insufficient unreserved budget for this model request")
            call_id = f"call_{uuid.uuid4().hex}"
            cost = (input_tokens * input_rate + allowance * output_rate) / 1_000_000
            conn.execute(
                insert(model_reservations).values(
                    reservation_id=call_id,
                    run_id=run_id,
                    step=step,
                    model=model,
                    tokens=input_tokens + allowance,
                    cost_usd=cost,
                    status="pending",
                    created_at=now,
                )
            )
            return call_id, allowance

    def settle(
        self,
        call_id: str,
        *,
        now: datetime,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        if min(input_tokens, output_tokens, cost_usd) < 0 or not math.isfinite(cost_usd):
            raise InvalidInputError("provider usage must be finite and nonnegative")
        with self.transaction() as conn:
            row = (
                conn.execute(select(model_reservations).where(model_reservations.c.reservation_id == call_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFoundError(f"model reservation {call_id} not found")
            if row["status"] == "settled":
                return
            conn.execute(
                insert(s.model_usage).values(
                    run_id=row["run_id"],
                    step=row["step"],
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    created_at=now,
                )
            )
            conn.execute(
                update(model_reservations)
                .where(model_reservations.c.reservation_id == call_id)
                .values(status="settled")
            )

    def uncertain(self, call_id: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                update(model_reservations)
                .where(
                    model_reservations.c.reservation_id == call_id,
                    model_reservations.c.status == "pending",
                )
                .values(status="uncertain")
            )

    def outstanding(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    select(model_reservations)
                    .where(model_reservations.c.status.in_(("pending", "uncertain")))
                    .order_by(model_reservations.c.created_at)
                ).mappings()
            ]

    def reconcile(
        self,
        call_id: str,
        *,
        actor: str,
        reason: str,
        confirmed_finished: bool,
        now: datetime,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """Privileged operator records verified provider usage after a lost response.

        Caller must stop/reconcile the originating worker and verify provider billing;
        a guessed zero refund or a still-running request is not safe reconciliation.
        """
        if not confirmed_finished or not actor.strip() or len(reason.strip()) < 10:
            raise InvalidInputError(
                "reconciliation requires a named operator, evidence reason, and confirmation the call finished"
            )
        if min(input_tokens, output_tokens, cost_usd) < 0 or not math.isfinite(cost_usd):
            raise InvalidInputError("provider usage must be finite and nonnegative")
        with self.transaction() as conn:
            row = (
                conn.execute(select(model_reservations).where(model_reservations.c.reservation_id == call_id))
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFoundError(f"model reservation {call_id} not found")
            if row["status"] == "settled":
                raise InvalidInputError("this call is already settled")
            conn.execute(
                insert(s.model_usage).values(
                    run_id=row["run_id"],
                    step=row["step"],
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    created_at=now,
                )
            )
            payload = {
                "reservation_id": call_id,
                "reason": reason,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            }
            conn.execute(
                insert(s.audit_events).values(
                    run_id=row["run_id"],
                    step=row["step"],
                    actor=actor,
                    event_type="model_usage_reconciled",
                    payload=payload,
                    payload_hash=sha256_hex(canonical_json(payload)),
                    created_at=now,
                )
            )
            conn.execute(
                update(model_reservations)
                .where(model_reservations.c.reservation_id == call_id)
                .values(status="settled")
            )
