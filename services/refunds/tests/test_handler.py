"""End-to-end tests for the Auto-Refund handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from refunds import (
    InMemoryChargebackRegistry,
    InMemoryIdempotencyStore,
    InMemoryNotifier,
    MovementKind,
    RefundHandler,
    ResultStatus,
    StubPaymentsClient,
)

from .conftest import make_event


class CountingPayments:
    """Wraps StubPaymentsClient to count refund/void calls (keeps idempotency)."""

    def __init__(self) -> None:
        self._inner = StubPaymentsClient()
        self.refund_calls = 0
        self.void_calls = 0

    def refund(self, order_id: str, amount: int, idempotency_key: str):
        self.refund_calls += 1
        return self._inner.refund(order_id, amount, idempotency_key)

    def void(self, order_id: str, idempotency_key: str):
        self.void_calls += 1
        return self._inner.void(order_id, idempotency_key)


# --- happy path REFUND ------------------------------------------------------


def test_happy_path_refund(notifier, chargebacks):
    payments = CountingPayments()
    handler = RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )

    result = handler.handle_raw(make_event(failure_reason="no_courier_assigned"))

    assert result.status is ResultStatus.PROCESSED
    assert result.decision.kind is MovementKind.REFUND
    assert payments.refund_calls == 1
    assert payments.void_calls == 0
    # Refund the full captured total.
    assert result.transaction is not None
    assert result.transaction.kind == "refund"
    assert result.transaction.amount == 2304
    # Exactly one notification, to the right customer.
    assert len(notifier.sent) == 1
    assert notifier.sent[0].customer_id == "cus_77d1"
    assert notifier.sent[0].amount == 2304
    assert not result.replayed


# --- happy path VOID --------------------------------------------------------


def test_happy_path_void(notifier, chargebacks):
    payments = CountingPayments()
    handler = RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )

    result = handler.handle_raw(
        make_event(failure_reason="payment_void_pre_capture")
    )

    assert result.status is ResultStatus.PROCESSED
    assert result.decision.kind is MovementKind.VOID
    assert payments.void_calls == 1
    assert payments.refund_calls == 0
    assert result.transaction is not None
    assert result.transaction.kind == "void"
    assert len(notifier.sent) == 1
    assert notifier.sent[0].kind == "void"


# --- double-fire idempotency ------------------------------------------------


def test_double_fire_is_idempotent(notifier, chargebacks):
    payments = CountingPayments()
    handler = RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )
    event = make_event(failure_reason="no_courier_assigned")

    first = handler.handle_raw(event)
    second = handler.handle_raw(event)  # exact same event fired again

    # Only ONE money movement and ONE notification.
    assert payments.refund_calls == 1
    assert len(notifier.sent) == 1
    # Second call returns the original result, flagged as a replay.
    assert second.replayed is True
    assert first.replayed is False
    assert second.transaction == first.transaction
    assert second.status is ResultStatus.PROCESSED


# --- chargeback dedup -------------------------------------------------------


def test_chargeback_suppresses_refund(notifier):
    payments = CountingPayments()
    chargebacks = InMemoryChargebackRegistry({"ord_test_001"})
    handler = RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )

    result = handler.handle_raw(make_event(failure_reason="merchant_cancelled"))

    assert result.status is ResultStatus.SUPPRESSED_CHARGEBACK
    assert payments.refund_calls == 0
    assert payments.void_calls == 0
    assert result.transaction is None
    # No refund notification on suppression.
    assert notifier.sent == []


# --- self-reported gating ---------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    ["never_delivered_claim", "missing_items_claim", "wrong_items_claim"],
)
def test_self_reported_reasons_are_gated(reason, notifier, chargebacks):
    payments = CountingPayments()
    handler = RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )

    result = handler.handle_raw(
        make_event(failure_reason=reason, confidence="self_reported")
    )

    assert result.status is ResultStatus.NOT_AUTO_ELIGIBLE
    assert payments.refund_calls == 0
    assert payments.void_calls == 0
    assert result.transaction is None
    assert notifier.sent == []


# --- loads the schema example end-to-end ------------------------------------


def test_processes_schema_example(handler):
    example_path = (
        Path(__file__).resolve().parents[3]
        / "schemas"
        / "order_failed.example.json"
    )
    payload = json.loads(example_path.read_text())

    result = handler.handle_raw(payload)

    # The example is no_courier_assigned -> refund of total 2304.
    assert result.status is ResultStatus.PROCESSED
    assert result.decision.kind is MovementKind.REFUND
    assert result.transaction is not None
    assert result.transaction.amount == 2304
    assert result.order_id == "ord_8f3a2c19"
    assert result.idempotency_key == "ord_8f3a2c19:att_01"
