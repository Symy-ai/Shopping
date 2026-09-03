"""Pure constitution helpers with typed boundaries."""

from __future__ import annotations

from urllib.parse import quote

from ..context import Context, ProductCard, SearchFilters

_HOTLINK_HOSTS = ("ddimg.cn", "piaojia.cn", "yiwugo.com")


def effective_search_filters(filters: SearchFilters, context: Context) -> tuple[SearchFilters, bool]:
    """Apply budget discipline without mutating the caller's typed input."""
    if context.budget_cents is None:
        return filters, False
    if filters.price_max_cents is not None and filters.price_max_cents <= context.budget_cents:
        return filters, False
    updated = filters.model_copy(update={"price_max_cents": context.budget_cents})
    return updated, True


def route_category(filters: SearchFilters) -> str:
    """The category field alone selects the retrieval strategy."""
    if filters.category:
        return filters.category
    if filters.subcategory and filters.subcategory.endswith("_ticket"):
        return "ticket"
    return "goods"


def proxy_image_url(image_url: str, proxy_base: str) -> str:
    """Route known hotlink-protected hosts through the configured proxy."""
    if not proxy_base or not image_url.startswith(("http://", "https://")):
        return image_url
    host = image_url.split("/", 3)[2]
    if not any(domain in host for domain in _HOTLINK_HOSTS):
        return image_url
    base = proxy_base.rstrip("/")
    if not base.endswith("/img"):
        base = f"{base}/img"
    return f"{base}?url={quote(image_url, safe=':/?&=')}"


def apply_image_proxy(cards: list[ProductCard], proxy_base: str) -> list[ProductCard]:
    return [card.model_copy(update={"image_url": proxy_image_url(card.image_url, proxy_base)}) for card in cards]


def stateless_projection(envelope: dict) -> dict:
    """Project away only the documented non-business response field."""
    return {key: value for key, value in envelope.items() if key != "trace_id"}
