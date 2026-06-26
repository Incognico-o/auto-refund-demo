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


# fix #1: idempotency_key shape must be "{order_id}:{attempt_id}".


def test_idempotency_key_must_match_order_and_attempt():
    bad = make_event(idempotency_key="ord_test_001:att_99")  # attempt mismatch
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_idempotency_key_wrong_order_rejected():
    bad = make_event(idempotency_key="ord_other:att_01")  # order mismatch
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_valid_idempotency_key_accepted():
    event = parse_order_failed(
        make_event(order_id="ord_x", attempt_id="att_7", idempotency_key="ord_x:att_7")
    )
    assert event.idempotency_key == "ord_x:att_7"


# fix #3: captured_amount.total must equal subtotal+fees+tax+tip+promo.


def test_inconsistent_total_rejected():
    bad = make_event()
    bad["captured_amount"]["total"] = 9999  # != 1840+399+165+400-500
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_consistent_total_accepted():
    # 1840 + 399 + 165 + 400 - 500 == 2304 (the schema example's figures).
    event = parse_order_failed(make_event())
    assert event.captured_amount.total == 2304


# fix #4: confidence must be consistent with the failure reason.


def test_deterministic_reason_with_self_reported_confidence_rejected():
    bad = make_event(
        failure_reason="no_courier_assigned", confidence="self_reported"
    )
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_self_reported_reason_with_deterministic_confidence_rejected():
    bad = make_event(
        failure_reason="never_delivered_claim", confidence="deterministic"
    )
    with pytest.raises(EventValidationError):
        parse_order_failed(bad)


def test_deterministic_reason_allows_corroborated_confidence():
    event = parse_order_failed(
        make_event(failure_reason="merchant_cancelled", confidence="corroborated")
    )
    assert event.confidence == "corroborated"
