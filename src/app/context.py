"""Shared request contracts and response envelope."""

from __future__ import annotations

import secrets
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Language = Literal["en", "zh"]
ErrorCode = Literal[
    "INVALID_INPUT",
    "CART_ITEM_NOT_FOUND",
    "CART_EMPTY",
    "PROVIDER_TIMEOUT",
    "PROVIDER_UNAVAILABLE",
    "SAFETY_BLOCKED",
    "INTERNAL_ERROR",
]
BUDGET_WARNING_CODE = "BUDGET_EXCEEDED_WARNING"


class Context(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_ref: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    session_ref: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    lang: Language
    currency: Annotated[str, StringConstraints(min_length=3, max_length=3)]
    budget_cents: int | None = Field(default=None, ge=0)
    cart_total_cents: int | None = Field(default=None, ge=0)


class ProductCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str
    title: str
    price_cents: int = Field(ge=0)
    unit_price_cents: int | None = Field(default=None, ge=0)
    unit_label: str | None = None
    currency: str
    category: str
    subcategory: str
    image_url: str
    source: str
    marketplace_url: str
    in_stock: bool
    compliance: list[str] = Field(default_factory=list)
    price_cents_display: str | None = None
    unit_price_cents_display: str | None = None


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Literal["goods", "local_service", "ticket"] | None = None
    subcategory: str | None = None
    price_min_cents: int | None = Field(default=None, ge=0)
    price_max_cents: int | None = Field(default=None, ge=0)


class CompareReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str | None = Field(default=None, min_length=1)
    product_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_exactly_one(self) -> "CompareReference":
        if (self.query is not None) == (self.product_ref is not None):
            raise ValueError("exactly one of query or product_ref is required")
        return self


class CartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str | None = Field(default=None, min_length=1)
    qty: int = Field(default=1, ge=1, le=1000)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class SearchData(BaseModel):
    cards: list[ProductCard]
    total_hits: int = Field(ge=0)
    applied_filters: SearchFilters
    message: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)


class CartLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str
    title: str
    qty: int = Field(ge=1)
    price_cents: int = Field(ge=0)
    currency: str
    image_url: str | None = None
    unit_price_cents: int | None = Field(default=None, ge=0)


class CartData(BaseModel):
    cart_lines: list[CartLine]
    cart_total_cents: int = Field(ge=0)
    warnings: list[dict[str, str]] = Field(default_factory=list)


class CompareData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ProductCard]
    unit_price_delta: int = Field(ge=0)
    verdict_hint: str
    notes: list[str] = Field(default_factory=list)


class ChatData(BaseModel):
    reply_draft: str
    product_cards: list[ProductCard]
    actions: list[dict[str, Any]]
    warnings: list[dict[str, str]]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool


class ResponseEnvelope(BaseModel):
    trace_id: str
    ok: bool
    data: Any | None = None
    error: ErrorBody | None = None


def new_trace_id() -> str:
    return f"trace_{secrets.token_hex(8)}"
