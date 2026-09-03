"""File-backed cart provider for explicit local demonstration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class CartDomainError(LookupError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)
        self.code = code

from .catalog_stub import ITEMS


class CartRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str
    title: str
    qty: int = Field(ge=1)
    price_cents: int = Field(ge=0)
    currency: str = "CNY"
    image_url: str | None = None
    unit_price_cents: int | None = Field(default=None, ge=0)


class CartProvider(Protocol):
    async def add(self, user_ref: str, product_ref: str, qty: int) -> list[CartRecord]: ...
    async def remove(self, user_ref: str, product_ref: str) -> list[CartRecord]: ...
    async def list(self, user_ref: str) -> list[CartRecord]: ...
    async def clear(self, user_ref: str) -> None: ...


class StubCartProvider(CartProvider):
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    async def add(self, user_ref: str, product_ref: str, qty: int) -> list[CartRecord]:
        item = next((entry for entry in ITEMS if entry.product_ref == product_ref), None)
        if item is None:
            raise CartDomainError("CART_ITEM_NOT_FOUND", "item is not in the catalog")
        lines = self._read(user_ref)
        existing = next((line for line in lines if line.product_ref == product_ref), None)
        if existing:
            existing.qty += qty
        else:
            lines.append(CartRecord(
                product_ref=item.product_ref,
                title=item.title,
                qty=qty,
                price_cents=item.price_cents,
                currency=item.currency,
                image_url=item.image_url,
                unit_price_cents=item.unit_price_cents,
            ))
        self._write(user_ref, lines)
        return lines

    async def remove(self, user_ref: str, product_ref: str) -> list[CartRecord]:
        lines = self._read(user_ref)
        if not any(line.product_ref == product_ref for line in lines):
            raise CartDomainError("CART_ITEM_NOT_FOUND", "item is not in the cart")
        lines = [line for line in lines if line.product_ref != product_ref]
        self._write(user_ref, lines)
        return lines

    async def list(self, user_ref: str) -> list[CartRecord]:
        return self._read(user_ref)

    async def clear(self, user_ref: str) -> None:
        self._write(user_ref, [])

    def _read(self, user_ref: str) -> list[CartRecord]:
        if not self._path.exists():
            return []
        raw = self._path.read_text(encoding="utf-8").strip()
        body: dict[str, Any] = json.loads(raw) if raw else {}
        return [CartRecord.model_validate(entry) for entry in body.get(user_ref, [])]

    def _write(self, user_ref: str, lines: list[CartRecord]) -> None:
        body: dict[str, Any] = {}
        if self._path.exists():
            raw = self._path.read_text(encoding="utf-8").strip()
            body = json.loads(raw) if raw else {}
        body[user_ref] = [line.model_dump(mode="json") for line in lines]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
