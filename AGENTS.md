# Agent context

Start with `README.md` for the product context and the **Orders vs. Payments** team boundary.

- Feature being scoped/built: **Auto-Refund** (auto-refund failed delivery orders).
- Failure event contract: `schemas/order_failed.example.json`.
- Cross-team contract (has open questions for the Payments team): `docs/payments-contract.DRAFT.md`.
- Build target: `services/refunds/`.

When scoping, keep self-reported failures (e.g. "never delivered") gated behind trust + caps; auto-refund deterministic, backend-recorded failures first.
