"""Typed model for the ``order_failed`` event.

Mirrors the shape in ``schemas/order_failed.example.json``. All monetary values
are integer minor units (cents) as emitted by the Order service; we do no
arithmetic on them here beyond carrying ``total`` through to Payments.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


# Failure reasons that are deterministic and backend-recorded. These are the
# only reasons in v1 auto-scope (see decision.py / the service README).
DETERMINISTIC_REASONS = frozenset(
    {
        "merchant_cancelled",
        "merchant_rejected",
        "store_closed_timeout",
        "no_courier_assigned",
        "payment_void_pre_capture",
    }
)

# Self-reported claims. Gated OUT of v1 auto-scope (trust score + dollar caps
# are explicitly future work). See README "Scope (v1)".
SELF_REPORTED_REASONS = frozenset(
    {
        "never_delivered_claim",
        "missing_items_claim",
        "wrong_items_claim",
    }
)

ALL_FAILURE_REASONS = DETERMINISTIC_REASONS | SELF_REPORTED_REASONS

VALID_CONFIDENCE = frozenset({"deterministic", "corroborated", "self_reported"})


class EventValidationError(ValueError):
    """Raised when an ``order_failed`` payload is malformed or incomplete."""


@dataclass(frozen=True)
class CapturedAmount:
    """Captured amount breakdown, in integer minor units (e.g. USD cents)."""

    currency: str
    subtotal: int
    fees: int
    tax: int
    tip: int
    promo: int
    total: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CapturedAmount":
        if not isinstance(data, Mapping):
            raise EventValidationError("captured_amount must be an object")
        try:
            return cls(
                currency=_require_str(data, "currency"),
                subtotal=_require_int(data, "subtotal"),
                fees=_require_int(data, "fees"),
                tax=_require_int(data, "tax"),
                tip=_require_int(data, "tip"),
                promo=_require_int(data, "promo"),
                total=_require_int(data, "total"),
            )
        except KeyError as exc:  # pragma: no cover - mapped to validation error
            raise EventValidationError(
                f"captured_amount missing field: {exc.args[0]}"
            ) from exc


@dataclass(frozen=True)
class OrderFailedEvent:
    """A parsed, validated ``order_failed`` event."""

    event: str
    version: str
    order_id: str
    attempt_id: str
    idempotency_key: str
    failure_reason: str
    confidence: str
    captured_amount: CapturedAmount
    merchant_id: str
    courier_id: str | None
    customer_id: str
    occurred_at: str

    @property
    def is_deterministic_reason(self) -> bool:
        return self.failure_reason in DETERMINISTIC_REASONS

    @property
    def is_self_reported_reason(self) -> bool:
        return self.failure_reason in SELF_REPORTED_REASONS


def parse_order_failed(data: Mapping[str, Any]) -> OrderFailedEvent:
    """Parse and validate a raw ``order_failed`` payload into a typed event.

    Raises :class:`EventValidationError` on any structural problem so callers
    can reject the message rather than silently moving money on bad input.
    """
    if not isinstance(data, Mapping):
        raise EventValidationError("event payload must be a JSON object")

    event = _require_str(data, "event")
    if event != "order_failed":
        raise EventValidationError(f"unexpected event type: {event!r}")

    failure_reason = _require_str(data, "failure_reason")
    if failure_reason not in ALL_FAILURE_REASONS:
        raise EventValidationError(f"unknown failure_reason: {failure_reason!r}")

    confidence = _require_str(data, "confidence")
    if confidence not in VALID_CONFIDENCE:
        raise EventValidationError(f"unknown confidence: {confidence!r}")

    if "captured_amount" not in data:
        raise EventValidationError("missing field: captured_amount")
    captured_amount = CapturedAmount.from_dict(data["captured_amount"])

    courier_id = data.get("courier_id")
    if courier_id is not None and not isinstance(courier_id, str):
        raise EventValidationError("courier_id must be a string or null")

    return OrderFailedEvent(
        event=event,
        version=_require_str(data, "version"),
        order_id=_require_str(data, "order_id"),
        attempt_id=_require_str(data, "attempt_id"),
        idempotency_key=_require_str(data, "idempotency_key"),
        failure_reason=failure_reason,
        confidence=confidence,
        captured_amount=captured_amount,
        merchant_id=_require_str(data, "merchant_id"),
        courier_id=courier_id,
        customer_id=_require_str(data, "customer_id"),
        occurred_at=_require_str(data, "occurred_at"),
    )


def _require_str(data: Mapping[str, Any], key: str) -> str:
    if key not in data:
        raise EventValidationError(f"missing field: {key}")
    value = data[key]
    if not isinstance(value, str) or value == "":
        raise EventValidationError(f"field {key} must be a non-empty string")
    return value


def _require_int(data: Mapping[str, Any], key: str) -> int:
    if key not in data:
        raise KeyError(key)
    value = data[key]
    # bool is a subclass of int; reject it explicitly to avoid silent coercion.
    if isinstance(value, bool) or not isinstance(value, int):
        raise EventValidationError(f"field {key} must be an integer (minor units)")
    return value
