"""Customer notification interface + an in-memory stub.

On a successful void/refund we record a customer-facing notification. Sending is
idempotent on the event idempotency key so a double-fire never produces a
duplicate notification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Notification:
    """A customer-facing refund/void notification."""

    customer_id: str
    order_id: str
    kind: str  # "refund" | "void"
    amount: int  # minor units
    message: str
    idempotency_key: str


class Notifier(Protocol):
    """Interface the handler depends on (injectable)."""

    def notify(self, notification: Notification) -> Notification: ...


class InMemoryNotifier:
    """Records notifications in memory; idempotent on ``idempotency_key``.

    A repeat ``notify`` with the same key returns the original notification and
    does not append a duplicate.
    """

    def __init__(self) -> None:
        self.sent: list[Notification] = []
        self._by_key: dict[str, Notification] = {}

    def notify(self, notification: Notification) -> Notification:
        existing = self._by_key.get(notification.idempotency_key)
        if existing is not None:
            return existing
        self._by_key[notification.idempotency_key] = notification
        self.sent.append(notification)
        return notification


def build_message(kind: str, amount: int, currency: str) -> str:
    """Human-readable status message for the customer."""
    if kind == "void":
        return (
            "Your order failed and the pending charge has been cancelled — "
            "you won't be billed."
        )
    dollars = amount / 100
    return (
        f"Your order failed, so we've refunded {dollars:.2f} {currency}. "
        "It should reappear on your payment method shortly."
    )
