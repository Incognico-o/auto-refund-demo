"""Payments client interface + an in-process stub.

In production the Payments team owns money movement and the transaction
source-of-truth; this is the thin client we'd call. For the MVP we ship a
deterministic stub (no network) that itself honors the idempotency key:
calling ``refund``/``void`` twice with the same key returns the same record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TransactionRecord:
    """A money-movement record as returned by Payments."""

    transaction_id: str
    status: str  # e.g. "succeeded"
    kind: str  # "refund" | "void"
    amount: int  # minor units
    idempotency_key: str


class PaymentsClient(Protocol):
    """Interface the handler depends on (injectable)."""

    def refund(
        self, order_id: str, amount: int, idempotency_key: str
    ) -> TransactionRecord: ...

    def void(
        self, order_id: str, idempotency_key: str
    ) -> TransactionRecord: ...


class StubPaymentsClient:
    """Deterministic, network-free Payments client for the MVP.

    Idempotent by ``idempotency_key``: the first call records a transaction; a
    repeat call with the same key returns the identical record (mirroring the
    real Payments dedup contract). A repeat with the same key but a different
    kind/amount is a programming error and raises.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, TransactionRecord] = {}

    def refund(
        self, order_id: str, amount: int, idempotency_key: str
    ) -> TransactionRecord:
        return self._record(
            kind="refund",
            order_id=order_id,
            amount=amount,
            idempotency_key=idempotency_key,
        )

    def void(self, order_id: str, idempotency_key: str) -> TransactionRecord:
        # A void releases the full pre-capture authorization; amount is 0 here
        # because nothing was captured/settled.
        return self._record(
            kind="void",
            order_id=order_id,
            amount=0,
            idempotency_key=idempotency_key,
        )

    def _record(
        self, kind: str, order_id: str, amount: int, idempotency_key: str
    ) -> TransactionRecord:
        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            if existing.kind != kind or existing.amount != amount:
                raise ValueError(
                    f"idempotency_key {idempotency_key!r} reused with different "
                    f"movement ({existing.kind}/{existing.amount} vs "
                    f"{kind}/{amount})"
                )
            return existing

        # Deterministic id derived from the idempotency key so the same logical
        # movement always yields the same transaction id (no randomness/clock).
        record = TransactionRecord(
            transaction_id=f"txn_{kind}_{idempotency_key}",
            status="succeeded",
            kind=kind,
            amount=amount,
            idempotency_key=idempotency_key,
        )
        self._by_key[idempotency_key] = record
        return record
