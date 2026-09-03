"""Supabase cart persistence adapter for the documented cart_lines table."""

from __future__ import annotations

from typing import Any

import httpx
from httpx import AsyncClient

from .cart_stub import CartDomainError, CartRecord
from .catalog_stub import CatalogProvider


class SupabaseCartProvider:
    def __init__(self, base_url: str, api_key: str, catalog: CatalogProvider) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._catalog = catalog

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            async with AsyncClient(timeout=10) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._headers(headers),
                    json=json,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise TimeoutError("cart provider timeout") from exc
        except httpx.HTTPError as exc:
            raise ConnectionError("cart provider unavailable") from exc

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
        }
        return headers | (extra or {})

    async def add(self, user_ref: str, product_ref: str, qty: int) -> list[CartRecord]:
        item = await self._catalog.get(product_ref)
        if item is None:
            raise LookupError("CART_ITEM_NOT_FOUND")
        rows = await self.list(user_ref)
        existing = next(
            (line for line in rows if line.product_ref == product_ref),
            None,
        )
        payload = {
            "user_ref": user_ref,
            "product_ref": product_ref,
            "title": item.title,
            "price_cents": item.price_cents,
            "currency": item.currency,
            "qty": qty + (existing.qty if existing else 0),
            "image_url": item.image_url,
        }
        await self._request(
            "POST",
            "/rest/v1/cart_lines",
            payload,
            {"Prefer": "resolution=merge-duplicates"},
        )
        return await self.list(user_ref)

    async def remove(self, user_ref: str, product_ref: str) -> list[CartRecord]:
        rows = await self.list(user_ref)
        if not any(line.product_ref == product_ref for line in rows):
            raise CartDomainError("CART_ITEM_NOT_FOUND", "item is not in the cart")
        await self._request(
            "DELETE",
            f"/rest/v1/cart_lines?user_ref=eq.{user_ref}&product_ref=eq.{product_ref}",
        )
        return await self.list(user_ref)

    async def list(self, user_ref: str) -> list[CartRecord]:
        rows = await self._request(
            "GET", f"/rest/v1/cart_lines?user_ref=eq.{user_ref}&select=*"
        )
        lines = [CartRecord.model_validate(row) for row in rows]
        for line in lines:
            item = await self._catalog.get(line.product_ref)
            if item is not None:
                line.unit_price_cents = item.unit_price_cents
        return lines

    async def clear(self, user_ref: str) -> None:
        await self._request("DELETE", f"/rest/v1/cart_lines?user_ref=eq.{user_ref}")
