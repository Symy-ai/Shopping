# Case 12 — add over-budget item succeeds with warning (required live run)

## Live legacy request

- `POST /cart/999999` sent item `陈年贵州酱香白酒 1L`, amount 1, price 1280, URL, and image.
- Response: `401 {"detail":"Missing bearer token"}`.
- Authorization setup failed because orchestrator could not reach memory (`502`). No line was added and the cart remained empty.

## Walkthrough projection

Legacy `CartAgent._maybe_impulse_budget_note` appends a gentle budget note only after a successful add; it does not pre-block. `CartCapability` keeps add successful and emits machine-readable `BUDGET_EXCEEDED_WARNING`. The single-item warning is emitted even when the existing cart total remains within budget.

## Conclusion

The required live attempt is recorded, with the external auth/memory dependency unavailable. The critical semantic rule—success plus warning rather than silent blocking—is covered by unit tests and preserves legacy behavior in structured form.
