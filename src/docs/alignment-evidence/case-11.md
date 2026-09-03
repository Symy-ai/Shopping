# Case 11 — add baijiu ×1 and preserve image (required live run)

## Live legacy request

- `POST /cart/999999` sent item `贵州酱香白酒 500ml`, amount 1, price 328, HTTPS marketplace URL, and hotlink image URL.
- Response: `401 {"detail":"Missing bearer token"}`.
- `POST /auth/register` for `align-r2-test`: `502 {"detail":"Failed to reach memory service"}`.
- Final `GET /cart/999999`: `401`; the test cart remained empty and required no cleanup mutation.

## Walkthrough projection

Legacy `POST /cart/{user_id}` forwards the displayed product payload to memory with `idempotent: true`, preserving title, quantity, price, URL, and supplied image fields. `StubCartProvider.add` and `SupabaseCartProvider.add` persist and return `image_url` in `cart_lines`.

## Conclusion

The required live attempt is captured verbatim. Because the memory dependency was unavailable, image persistence is demonstrated by endpoint/code walkthrough and mock-backed tests. The new interface returns structured `cart_lines` rather than legacy prose.
