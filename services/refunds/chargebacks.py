"""Chargeback registry — the double-pay guard.

If a chargeback has already landed for an order, the customer is being made
whole through the dispute flow; auto-refunding would pay them twice. The handler
checks this registry and suppresses the refund if a chargeback exists.

(See "Double-pay guard" in docs/payments-contract.DRAFT.md.)
"""

from __future__ import annotations

from typing import Protocol


class ChargebackRegistry(Protocol):
    """Interface the handler depends on (injectable)."""

    def has_chargeback(self, order_id: str) -> bool: ...


class InMemoryChargebackRegistry:
    """Set-backed registry of orders with a landed chargeback."""

    def __init__(self, order_ids: set[str] | None = None) -> None:
        self._orders: set[str] = set(order_ids or set())

    def add(self, order_id: str) -> None:
        self._orders.add(order_id)

    def has_chargeback(self, order_id: str) -> bool:
        return order_id in self._orders
