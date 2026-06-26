# refunds service (Auto-Refund MVP)

Consumes `order_failed` (see `../../schemas/order_failed.example.json`) and, for
**deterministic, backend-recorded** failures, issues an **idempotent** void/refund
of the captured amount via the Payments client, then emits a customer notification.

## Scope (v1)

**Auto-process** (deterministic, backend-recorded):
`merchant_cancelled`, `merchant_rejected`, `store_closed_timeout`,
`no_courier_assigned`, `payment_void_pre_capture`.

**Gated out of v1** (self-reported claims — return `NOT_AUTO_ELIGIBLE`, no money
moved): `never_delivered_claim`, `missing_items_claim`, `wrong_items_claim`.
Trust-score / dollar-cap handling for these is explicitly future work.

### Void vs. refund (per `docs/payments-contract.DRAFT.md`)
- `payment_void_pre_capture` → **VOID** (funds not yet captured).
- any other deterministic reason → **REFUND** of `captured_amount.total`.

### Guards
- **Idempotency:** keyed on the event `idempotency_key` (`order_id:attempt_id`).
  A double-fire returns the original result — no second money movement, no
  duplicate notification. The Payments stub is independently idempotent too.
  The key shape is enforced at parse time, and a cache hit additionally verifies
  the stored result belongs to the same `order_id`/`attempt_id` (a collision
  raises `IdempotencyKeyCollision` rather than replaying the wrong result).
- **Double-pay / chargeback:** if a chargeback already landed for the order, the
  refund is **suppressed** (`SUPPRESSED_CHARGEBACK`) and no money is moved.

### Input validation (`parse_order_failed`)
Beyond per-field type checks, the parser rejects (`EventValidationError`):
- `idempotency_key` that isn't exactly `"{order_id}:{attempt_id}"`,
- `captured_amount.total` that doesn't equal `subtotal+fees+tax+tip+promo`
  (`promo` is negative),
- a `confidence` that contradicts the `failure_reason` (deterministic reasons
  can't be `self_reported`; self-reported claims must be `self_reported`).

### Void observability
A void moves `$0` (nothing was captured), so `TransactionRecord.amount == 0`.
The released pre-capture authorization is carried on
`TransactionRecord.authorized_amount` so a void is distinguishable from a genuine
`$0` event. `authorized_amount` is observability only — never treated as moved money.

## Layout

```
services/refunds/
├── __init__.py          # public API re-exports
├── models.py            # OrderFailedEvent / CapturedAmount + parse/validate
├── decision.py          # pure decide(): AUTO_PROCESS vs NOT_AUTO_ELIGIBLE, void vs refund
├── payments.py          # PaymentsClient protocol + idempotent StubPaymentsClient
├── notifications.py     # Notifier protocol + idempotent InMemoryNotifier
├── idempotency.py       # IdempotencyStore protocol + InMemoryIdempotencyStore
├── chargebacks.py       # ChargebackRegistry protocol + InMemoryChargebackRegistry
├── handler.py           # RefundHandler — wires it all together (collaborators injectable)
├── pyproject.toml       # packaging + pytest config (stdlib-only runtime)
├── requirements-dev.txt # dev dep: pytest
└── tests/               # pytest suite
```

All collaborators (payments, notifier, idempotency store, chargeback registry)
are **injectable** into `RefundHandler` for testing and later swap-out.

## Usage

```python
from refunds import RefundHandler

handler = RefundHandler()          # default in-memory stubs
result = handler.handle_raw(event_dict)
print(result.status)               # PROCESSED / NOT_AUTO_ELIGIBLE / SUPPRESSED_CHARGEBACK
```

## Running tests

Runtime is **standard-library only**; tests need `pytest`.

```bash
cd services/refunds
python -m pip install -r requirements-dev.txt   # or: pip install pytest
pytest
```
