"""Legacy search-service adapter; failures surface as provider errors."""

from __future__ import annotations

import httpx

from .catalog_stub import CatalogItem, CatalogProvider


class RemoteCatalogProvider(CatalogProvider):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def get(self, product_ref: str) -> CatalogItem | None:
        matches = await self.search(product_ref)
        return next((item for item in matches if item.product_ref == product_ref), None)

    async def search(self, query: str, *, category: str | None = None) -> list[CatalogItem]:
        filters: dict[str, object] = {}
        if category:
            filters["category"] = category
        payload = {
            "text": [query],
            "categories": [category] if category else [],
            "filters": filters,
            "k": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(f"{self._base_url}/query/text", json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError("catalog provider timeout") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ConnectionError("catalog provider unavailable") from exc

        cards: list[CatalogItem] = []
        for index, product_ref in enumerate(body.get("ids", [])):
            cards.append(CatalogItem(
                product_ref=str(product_ref),
                title=body.get("names", [""] * (index + 1))[index],
                price_cents=int(float(body.get("prices", [0] * (index + 1))[index] or 0) * 100),
                currency=body.get("currencies", ["CNY"] * (index + 1))[index],
                category="goods",
                subcategory="legacy",
                image_url=body.get("images", [""] * (index + 1))[index],
                source=body.get("urls", [""] * (index + 1))[index],
                marketplace_url=body.get("urls", [""] * (index + 1))[index],
            ))
        return cards
