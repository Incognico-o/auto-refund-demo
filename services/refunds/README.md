# refunds service (build target)

Build the **Auto-Refund MVP** here.

**Scope (v1):** consume `order_failed`, and for **deterministic, backend-recorded** failures
(`merchant_cancelled`, `merchant_rejected`, `store_closed_timeout`, `no_courier_assigned`,
`payment_void_pre_capture`) issue an **idempotent** refund/void of the captured amount via the
Payments client, then emit a customer notification.

Gate self-reported failures (`never_delivered_claim`, `missing_items_claim`, `wrong_items_claim`)
behind a trust score + dollar caps — out of v1 auto-scope.

**Expected pieces:**
- `order_failed` consumer/hook
- idempotent refund decision (void-before-capture vs. refund-after) per `docs/payments-contract.DRAFT.md`
- a Payments client stub
- tests (happy path + double-fire idempotency + chargeback dedup)

_Empty until the agents build it._
