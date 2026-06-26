"""Unit tests for decision logic and event parsing/validation."""

from __future__ import annotations

import pytest

from refunds import DecisionType, MovementKind, decide, parse_order_failed
from refunds.models import EventValidationError

from .conftest import make_event


# --- decision logic ---------------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "merchant_cancelled",
        "merchant_rejected",
        "store_closed_timeout",
        "no_courier_assigned",
    ],
)
def test_deterministic_post_capture_reasons_refund(reason):
    event = parse_order_failed(make_event(failure_reason=reason))
    decision = decide(event)
    assert decision.decision is DecisionType.AUTO_PROCESS
    assert decision.kind is MovementKind.REFUND
    assert decision.amount == 2304


def test_pre_capture_voids():
    event = parse_order_failed(
        make_event(failure_reason="payment_void_pre_capture")
    )
    decision = decide(event)
    assert decision.decision is DecisionType.AUTO_PROCESS
    assert decision.kind is MovementKind.VOID


@pytest.mark.parametrize(
    "reason",
    ["never_delivered_claim", "missing_items_claim", "wrong_items_claim"],
)
def test_self_reported_not_eligible(reason):
    event = parse_order_failed(
        make_event(failure_reason=reason, confidence="self_reported")
    )
    decision = decide(event)
    assert decision.decision is DecisionType.NOT_AUTO_ELIGIBLE
    assert decision.kind is MovementKind.NONE
    assert decision.amount is None


# --- parsing / validation ---------------------------------------------------


def test_parse_valid_event():
    event = parse_order_failed(make_event())
    assert event.order_id == "ord_test_001"
    assert event.captured_amount.total == 2304
    assert event.courier_id is None
    assert event.is_deterministic_reason


def test_unknown_failure_reason_rejected():
    with pytest.raises(EventValidationError):
        parse_order_failed(make_event(failure_reason="aliens_took_it"))


def test_wrong_event_type_rejected():
    with pytest.raises(EventValidationError):
        parse_order_failed(make_event(event="order_created"))


def test_missing_required_field_rejected():
    bad = make_event()
    del bad["customer_id"]
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_non_integer_amount_rejected():
    bad = make_event()
    bad["captured_amount"]["total"] = "2304"  # string, not int
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)
