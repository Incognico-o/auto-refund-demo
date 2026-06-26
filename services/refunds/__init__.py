"""Auto-Refund MVP (Orders side).

Consumes ``order_failed`` events and, for deterministic backend-recorded
failures, issues an idempotent void/refund via the Payments client and emits a
customer notification.

See ``services/refunds/README.md`` for scope and the cross-team contract in
``docs/payments-contract.DRAFT.md``.
"""

from .models import OrderFailedEvent, CapturedAmount, parse_order_failed
from .decision import Decision, DecisionType, MovementKind, decide
from .payments import PaymentsClient, StubPaymentsClient, TransactionRecord
from .notifications import Notifier, InMemoryNotifier, Notification
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore
from .chargebacks import ChargebackRegistry, InMemoryChargebackRegistry
from .handler import RefundHandler, RefundResult, ResultStatus

__all__ = [
    "OrderFailedEvent",
    "CapturedAmount",
    "parse_order_failed",
    "Decision",
    "DecisionType",
    "MovementKind",
    "decide",
    "PaymentsClient",
    "StubPaymentsClient",
    "TransactionRecord",
    "Notifier",
    "InMemoryNotifier",
    "Notification",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "ChargebackRegistry",
    "InMemoryChargebackRegistry",
    "RefundHandler",
    "RefundResult",
    "ResultStatus",
]
