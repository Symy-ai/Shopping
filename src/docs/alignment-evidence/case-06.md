# Case 06 — compare two baijiu (required live run)

## Live legacy request

- Requested `GET /cart/999999`, `POST /cart/999999`, and the final read again on 2026-09-02.
- The cart endpoints returned `401 {"detail":"Missing bearer token"}`.
- Registering `align-r2-test` returned `502 {"detail":"Failed to reach memory service"}`, so an authorized cart-side run was impossible without restarting services, which Round 2 forbids.
- No legacy cart state changed.

## Walkthrough projection

`orchestrator/app/agents/cartops/catalog_match.py` normalizes names, resolves catalog candidates, extracts the embedded `PRICE:` field, and prefers exact, containment, and token-overlap matches. `CompareCapability` preserves A/B resolution, orders by normalized unit price, and returns delta, verdict, and notes. Legacy has no native compare endpoint; its semantic equivalent is catalog matching plus deterministic price arithmetic.

## Conclusion

The required live attempt is recorded, but its authorization dependency was unavailable. Semantic alignment is established by code walkthrough. The new tool additionally exposes unit-price normalization, warnings, and language-aware notes.
