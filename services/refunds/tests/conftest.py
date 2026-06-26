"""Shared fixtures and event builders for the refunds test suite."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from refunds import (
    InMemoryChargebackRegistry,
    InMemoryIdempotencyStore,
    InMemoryNotifier,
    RefundHandler,
    StubPaymentsClient,
)


# A deterministic-failure base event (no_courier_assigned). Tests copy + tweak.
BASE_EVENT: dict[str, Any] = {
    "event": "order_failed",
    "version": "0.1-draft",
    "order_id": "ord_test_001",
    "attempt_id": "att_01",
    "idempotency_key": "ord_test_001:att_01",
    "failure_reason": "no_courier_assigned",
    "confidence": "deterministic",
    "captured_amount": {
        "currency": "USD",
        "subtotal": 1840,
        "fees": 399,
        "tax": 165,
        "tip": 400,
        "promo": -500,
        "total": 2304,
    },
    "merchant_id": "mer_4421",
    "courier_id": None,
    "customer_id": "cus_77d1",
    "occurred_at": "2026-06-26T19:04:11Z",
}


def make_event(**overrides: Any) -> dict[str, Any]:
    """Return a deep copy of BASE_EVENT with top-level fields overridden.

    Passing ``failure_reason`` keeps idempotency_key consistent unless the
    caller also overrides ``idempotency_key`` / ids explicitly.
    """
    event = copy.deepcopy(BASE_EVENT)
    event.update(overrides)
    return event


@pytest.fixture
def payments() -> StubPaymentsClient:
    return StubPaymentsClient()


@pytest.fixture
def notifier() -> InMemoryNotifier:
    return InMemoryNotifier()


@pytest.fixture
def chargebacks() -> InMemoryChargebackRegistry:
    return InMemoryChargebackRegistry()


@pytest.fixture
def handler(
    payments: StubPaymentsClient,
    notifier: InMemoryNotifier,
    chargebacks: InMemoryChargebackRegistry,
) -> RefundHandler:
    return RefundHandler(
        payments=payments,
        notifier=notifier,
        idempotency_store=InMemoryIdempotencyStore(),
        chargebacks=chargebacks,
    )
