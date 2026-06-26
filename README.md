# Auto-Refund — working context

Context repo for scoping and building **Auto-Refund** at our food-delivery app. Cloned into the Omnigent sandbox as the session's working directory so agents start grounded — no long brief needed.

## The app
A food-delivery marketplace: **customers** order from **merchants**; **couriers** deliver. Today, when an order fails, the customer taps **"report a problem"** and waits days for a human to issue a refund.

## The initiative: Auto-Refund
When an order fails — never delivered, cancelled before it arrives, or missing/wrong items — refund the customer **automatically and immediately**, turning a multi-day complaint into a sub-minute resolution.

## What exists today
- **Order service** (our team) emits order lifecycle events; it knows when an order is cancelled, times out, or a courier is never assigned. It will emit the new `order_failed` event (see `schemas/order_failed.example.json`).
- **Payments service** (Payments team) owns charges, captures, refunds, voids, and the transaction record. It exposes refund/void APIs.
- Refunds today are **manual**, opened via support tickets.

## Team boundaries (important)
- **Orders (us):** *detect* the failure and decide a refund is owed. Emits `order_failed`.
- **Payments (them):** *move the money* — void vs. refund, idempotency, partial refunds, chargeback reconciliation, and source-of-truth for the transaction.

The contract between us is a **draft** with open questions — see `docs/payments-contract.DRAFT.md`.

## Where to build
The Auto-Refund MVP service lives in `services/refunds/` (see its README).
