"""Refund / void decision logic.

This encodes the v1 auto-scope from ``services/refunds/README.md`` and the
void-vs-refund mapping proposed in ``docs/payments-contract.DRAFT.md``.

Pure function: no money is moved here. The handler turns an eligible decision
into an actual Payments call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import OrderFailedEvent


class DecisionType(str, Enum):
    """Outcome of evaluating an event against v1 auto-scope."""

    AUTO_PROCESS = "AUTO_PROCESS"  # eligible -> move money
    NOT_AUTO_ELIGIBLE = "NOT_AUTO_ELIGIBLE"  # gated out of v1 (self-reported)


class MovementKind(str, Enum):
    """Whether eligible money movement is a void or a refund."""

    VOID = "void"
    REFUND = "refund"
    NONE = "none"


@dataclass(frozen=True)
class Decision:
    """Result of :func:`decide` — what (if anything) we should ask Payments to do."""

    decision: DecisionType
    kind: MovementKind
    # Amount to move, in minor units. None when no movement is warranted.
    amount: int | None
    reason: str  # human/debug-friendly explanation, echoed into results


def decide(event: OrderFailedEvent) -> Decision:
    """Decide how to handle a failed order, per the contract and v1 scope.

    Rules:
      * Self-reported claims (never_delivered_claim, missing_items_claim,
        wrong_items_claim) are GATED OUT of v1 auto-scope -> NOT_AUTO_ELIGIBLE,
        no money movement. Trust-score / dollar-cap handling is future work.
      * Deterministic, backend-recorded reasons are AUTO_PROCESS.
          - payment_void_pre_capture  => VOID (money not yet captured)
          - everything else           => REFUND of captured_amount.total
        (See "Void vs. refund" in docs/payments-contract.DRAFT.md.)
    """
    if event.is_self_reported_reason:
        return Decision(
            decision=DecisionType.NOT_AUTO_ELIGIBLE,
            kind=MovementKind.NONE,
            amount=None,
            reason=(
                f"{event.failure_reason} is self-reported; gated out of v1 "
                "auto-scope (requires trust score + dollar caps)"
            ),
        )

    # Defensive: parse_order_failed only admits known reasons, so any reason
    # that is not self-reported is deterministic. Guard anyway.
    if not event.is_deterministic_reason:  # pragma: no cover - unreachable
        return Decision(
            decision=DecisionType.NOT_AUTO_ELIGIBLE,
            kind=MovementKind.NONE,
            amount=None,
            reason=f"{event.failure_reason} is not in v1 auto-scope",
        )

    if event.failure_reason == "payment_void_pre_capture":
        # Pre-capture: no settled funds yet, so we void rather than refund.
        return Decision(
            decision=DecisionType.AUTO_PROCESS,
            kind=MovementKind.VOID,
            amount=event.captured_amount.total,
            reason="payment_void_pre_capture -> void (pre-capture)",
        )

    # Post-capture deterministic failure: refund the full captured total.
    return Decision(
        decision=DecisionType.AUTO_PROCESS,
        kind=MovementKind.REFUND,
        amount=event.captured_amount.total,
        reason=f"{event.failure_reason} -> refund captured total",
    )
