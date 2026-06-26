# Orders → Payments: Auto-Refund contract (DRAFT)

**Status:** 🟡 DRAFT — open questions need the **Payments team**'s sign-off.

## The flow (proposed)
1. Order service detects a failed order and emits `order_failed` (see `../schemas/order_failed.example.json`).
2. Payments consumes it and decides **void** (pre-capture) or **refund** (post-capture).
3. Payments executes the money movement **idempotently** and remains source-of-truth for the transaction.

## What each team owns
| Orders (us) | Payments (them) |
|---|---|
| Detect failure, classify reason, emit `order_failed` | Void vs. refund decision + execution |
| Failure confidence / trust signals | Idempotency, dedup vs. chargebacks |
| Customer-facing "refund status" UX | Ledger, partial refunds, reconciliation |

## 🔴 Open questions for Payments (fill in during review)
- [ ] **Void vs. refund:** can we capture-at-pickup so most failures are a cheap pre-settlement void? Cost delta?
- [ ] **Idempotency key:** owned by us, Payments, or the PSP? Keyed on `order_id + attempt_id`?
- [ ] **Partial refunds:** how are missing-item refunds split across subtotal / fees / tax / tip / promo?
- [ ] **Double-pay guard:** how do we suppress a refund when a chargeback already landed?
- [ ] **Tip handling:** refund the tip when the courier was already paid? Who absorbs it?
- [ ] **Loss ownership:** platform vs. merchant vs. courier — and how/when do we claw back?
- [ ] **"Instant" SLA:** what funds-visible timing do we promise (initiate now, settle in N days)?
