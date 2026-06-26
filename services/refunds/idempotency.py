"""Idempotency store for money movement.

Keyed on the event ``idempotency_key`` (``order_id:attempt_id``). The handler
records the full :class:`RefundResult` so a double-fire returns the original
result without moving money a second time.

The MVP ships an in-memory implementation; the interface is injectable so a
durable store (Redis/DB) can be swapped in later.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


class IdempotencyStore(Protocol[T]):
    """Get/set keyed by idempotency key."""

    def get(self, key: str) -> T | None: ...

    def set(self, key: str, value: T) -> None: ...


class InMemoryIdempotencyStore(Generic[T]):
    """Simple dict-backed store. Not thread-safe; fine for the MVP."""

    def __init__(self) -> None:
        self._store: dict[str, T] = {}

    def get(self, key: str) -> T | None:
        return self._store.get(key)

    def set(self, key: str, value: T) -> None:
        self._store[key] = value
