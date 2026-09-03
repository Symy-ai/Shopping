# Cases 07–15 — code-walkthrough alignment projections

These cases were not required to be live-run by Round 2. Live runs were not repeated after the required runs established that authorized cart mutation could not reach memory.

- **07 category mismatch**: both cards are returned and a category-difference note explains that unit-price bases can differ.
- **08 same name, different size**: `unit_price_cents` is the ordering and delta key; `/100ml`, `/500ml`, and `/1L` prices are normalized before comparison.
- **09 one side unavailable**: the unavailable card remains visible, comparison succeeds, and a warning note identifies it.
- **10 two tickets**: both service cards return with `/adult` labels and a note to compare inclusions, duration, and redemption conditions.
- **13 remove missing**: the provider raises `CART_ITEM_NOT_FOUND`; the envelope maps it to the exact code and non-retryable semantics.
- **14 checkout empty**: the provider checks the list before clear; the envelope maps to `CART_EMPTY`.
- **15 list**: every line returns with image, unit price, and total, sorted by deterministic ascending unit price.
