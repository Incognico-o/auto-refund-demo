"""order_failed consumer/handler — wires decision + collaborators together.

Order of operations for an event:
  1. Parse/validate the payload into an :class:`OrderFailedEvent`.
  2. Idempotency: if we've already processed this idempotency_key, return the
     stored result (no second money movement, no duplicate notification).
  3. Decide (decision.decide): eligible AUTO_PROCESS vs gated NOT_AUTO_ELIGIBLE.
  4. Double-pay guard: if a chargeback already landed, SUPPRESS — no movement.
  5. Move money via the injected Payments client (refund or void).
  6. Record a customer notification (idempotent).
  7. Store and return the result.

All collaborators (payments, notifier, idempotency store, chargeback registry)
are injected so the handler is trivially testable and swappable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .chargebacks import ChargebackRegistry, InMemoryChargebackRegistry
from .decision import Decision, DecisionType, MovementKind, decide
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore
from .models import OrderFailedEvent, parse_order_failed
from .notifications import (
    InMemoryNotifier,
    Notification,
    Notifier,
    build_message,
)
from .payments import PaymentsClient, StubPaymentsClient, TransactionRecord


class IdempotencyKeyCollision(Exception):
    """Raised when an idempotency_key maps to a result for a different order.

    Signals corrupt input or a key-generation bug — never silently swallowed,
    because the safe action is to refuse rather than replay the wrong result.
    """


class ResultStatus(str, Enum):
    """Terminal status of handling an event."""

    PROCESSED = "PROCESSED"  # money moved (refund or void)
    NOT_AUTO_ELIGIBLE = "NOT_AUTO_ELIGIBLE"  # self-reported, gated out of v1
    SUPPRESSED_CHARGEBACK = "SUPPRESSED_CHARGEBACK"  # double-pay guard tripped


@dataclass(frozen=True)
class RefundResult:
    """Outcome of processing one ``order_failed`` event."""

    status: ResultStatus
    decision: Decision
    idempotency_key: str
    order_id: str
    # Request identity carried so a cache hit can verify the stored result
    # belongs to the SAME order/attempt (defense-in-depth for the replay guard).
    attempt_id: str = ""
    transaction: TransactionRecord | None = None
    notification: Notification | None = None
    # True only when returned from the idempotency cache on a replay.
    replayed: bool = False

    def with_replayed(self, value: bool) -> "RefundResult":
        return RefundResult(
            status=self.status,
            decision=self.decision,
            idempotency_key=self.idempotency_key,
            order_id=self.order_id,
            attempt_id=self.attempt_id,
            transaction=self.transaction,
            notification=self.notification,
            replayed=value,
        )


class RefundHandler:
    """Processes ``order_failed`` events. Collaborators are injectable."""

    def __init__(
        self,
        payments: PaymentsClient | None = None,
        notifier: Notifier | None = None,
        idempotency_store: IdempotencyStore[RefundResult] | None = None,
        chargebacks: ChargebackRegistry | None = None,
    ) -> None:
        self.payments: PaymentsClient = payments or StubPaymentsClient()
        self.notifier: Notifier = notifier or InMemoryNotifier()
        self.idempotency_store: IdempotencyStore[RefundResult] = (
            idempotency_store or InMemoryIdempotencyStore()
        )
        self.chargebacks: ChargebackRegistry = (
            chargebacks or InMemoryChargebackRegistry()
        )

    def handle_raw(self, payload: Mapping[str, Any]) -> RefundResult:
        """Entry point for a raw event dict (e.g. decoded JSON)."""
        event = parse_order_failed(payload)
        return self.handle(event)

    def handle(self, event: OrderFailedEvent) -> RefundResult:
        """Process a parsed event, idempotently."""
        key = event.idempotency_key

        # (2) Idempotency: replay the original result on a double-fire — but
        # only if the cached result is for the SAME order/attempt. fix #1 makes
        # the key shape "{order_id}:{attempt_id}", so a collision here should be
        # impossible; we still verify explicitly rather than risk returning
        # another order's transaction or moving money under a confused key.
        cached = self.idempotency_store.get(key)
        if cached is not None:
            if (
                cached.order_id != event.order_id
                or cached.attempt_id != event.attempt_id
            ):
                raise IdempotencyKeyCollision(
                    f"idempotency_key {key!r} already maps to "
                    f"{cached.order_id}:{cached.attempt_id}, refusing to replay "
                    f"for {event.order_id}:{event.attempt_id}"
                )
            return cached.with_replayed(True)

        # (3) Decide.
        decision = decide(event)

        if decision.decision is DecisionType.NOT_AUTO_ELIGIBLE:
            return self._finalize(
                event,
                RefundResult(
                    status=ResultStatus.NOT_AUTO_ELIGIBLE,
                    decision=decision,
                    idempotency_key=key,
                    order_id=event.order_id,
                    attempt_id=event.attempt_id,
                ),
            )

        # (4) Double-pay / chargeback guard — suppress before moving money.
        if self.chargebacks.has_chargeback(event.order_id):
            return self._finalize(
                event,
                RefundResult(
                    status=ResultStatus.SUPPRESSED_CHARGEBACK,
                    decision=decision,
                    idempotency_key=key,
                    order_id=event.order_id,
                    attempt_id=event.attempt_id,
                ),
            )

        # (5) Move money via Payments (itself idempotent on the same key).
        if decision.kind is MovementKind.VOID:
            # decision.amount is the captured/authorized total; pass it for
            # observability. The void moves $0 (nothing was captured).
            transaction = self.payments.void(
                order_id=event.order_id,
                idempotency_key=key,
                authorized_amount=decision.amount or 0,
            )
        elif decision.kind is MovementKind.REFUND:
            assert decision.amount is not None  # guaranteed for AUTO_PROCESS
            transaction = self.payments.refund(
                order_id=event.order_id,
                amount=decision.amount,
                idempotency_key=key,
            )
        else:  # pragma: no cover - AUTO_PROCESS always has a movement kind
            raise AssertionError("AUTO_PROCESS decision without a movement kind")

        # (6) Record a customer notification (idempotent on the same key).
        notification = self.notifier.notify(
            Notification(
                customer_id=event.customer_id,
                order_id=event.order_id,
                kind=transaction.kind,
                amount=transaction.amount,
                message=build_message(
                    kind=transaction.kind,
                    amount=transaction.amount,
                    currency=event.captured_amount.currency,
                ),
                idempotency_key=key,
            )
        )

        return self._finalize(
            event,
            RefundResult(
                status=ResultStatus.PROCESSED,
                decision=decision,
                idempotency_key=key,
                order_id=event.order_id,
                attempt_id=event.attempt_id,
                transaction=transaction,
                notification=notification,
            ),
        )

    def _finalize(
        self, event: OrderFailedEvent, result: RefundResult
    ) -> RefundResult:
        """Store the result under the idempotency key and return it."""
        self.idempotency_store.set(event.idempotency_key, result)
        return result
