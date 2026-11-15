# Refunds Service

Build the **Auto-Refund MVP** here.

## V1 Scope

Consume `order_failed` events for these **deterministic, backend-recorded** failures:

- `merchant_cancelled`
- `merchant_rejected`
- `store_closed_timeout`
- `no_courier_assigned`
- `payment_void_pre_capture`

For eligible failures:

1. Issue an **idempotent** refund or void of the captured amount through the Payments client.
2. Emit a customer notification.

## Out of Scope

Gate self-reported failures behind a trust score and dollar caps. These failures are not eligible
for automatic refunds in v1:

- `never_delivered_claim`
- `missing_items_claim`
- `wrong_items_claim`

## Expected Components

- An `order_failed` consumer or hook
- An idempotent refund decision (void before capture vs. refund after capture), following
  `docs/payments-contract.DRAFT.md`
- A Payments client stub
- Tests covering the happy path, double-fire idempotency, and chargeback deduplication

## Status

_Empty until the agents build it._
