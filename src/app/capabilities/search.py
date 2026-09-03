"""Stateless catalog search capability."""

from __future__ import annotations

from ..constitution.rules import (
    apply_image_proxy,
    effective_search_filters,
    route_category,
)
from ..context import ProductCard, SearchFilters, SearchData
from ..providers.catalog_stub import CatalogProvider, CatalogItem


class SearchCapability:
    def __init__(self, provider: CatalogProvider, image_proxy_base: str = "") -> None:
        self._provider = provider
        self._image_proxy_base = image_proxy_base

    async def execute(self, query: str, filters: SearchFilters, context: dict) -> SearchData:
        typed_filters = filters
        from ..context import Context
        typed_context = context if isinstance(context, Context) else Context.model_validate(context)
        effective, budget_applied = effective_search_filters(typed_filters, typed_context)
        category = route_category(typed_filters)
        candidates = await self._provider.search(query, category=category)
        cards = [
            self._card(item)
            for item in candidates
            if self._matches(item, typed_filters, effective, typed_context)
        ]
        cards.sort(key=lambda card: (
            card.unit_price_cents if card.unit_price_cents is not None else card.price_cents,
            card.product_ref,
        ))
        cards = apply_image_proxy(cards, self._image_proxy_base)
        if not cards:
            return SearchData(
                cards=[],
                total_hits=0,
                applied_filters=typed_filters,
                message=self._empty_message(typed_context.lang, budget_applied),
                actions=[{"type": "search", "payload": {"query": query, "filters": {}}}],
            )
        return SearchData(cards=cards, total_hits=len(cards), applied_filters=typed_filters)

    def _matches(self, item: CatalogItem, original: SearchFilters, effective: SearchFilters, context) -> bool:
        if original.category and item.category != original.category:
            return False
        if original.subcategory and item.subcategory != original.subcategory:
            return False
        if item.currency.upper() != context.currency.upper():
            return False
        if effective.price_min_cents is not None and item.price_cents < effective.price_min_cents:
            return False
        if effective.price_max_cents is not None and item.price_cents > effective.price_max_cents:
            return False
        return True

    def _card(self, item: CatalogItem) -> ProductCard:
        unit_price = item.unit_price_cents if item.unit_price_cents is not None else item.price_cents
        unit_label = item.unit_label or ("/1ea")
        return ProductCard(
            product_ref=item.product_ref,
            title=item.title,
            price_cents=item.price_cents,
            unit_price_cents=unit_price,
            unit_label=unit_label,
            currency=item.currency,
            category=item.category,
            subcategory=item.subcategory,
            image_url=item.image_url,
            source=item.source,
            marketplace_url=item.marketplace_url,
            in_stock=item.in_stock,
            compliance=item.compliance,
        )

    def _empty_message(self, lang: str, budget_applied: bool) -> str:
        if lang == "zh":
            return "预算范围内暂无匹配商品，可尝试放宽价格或预算。" if budget_applied else "暂无匹配商品，可尝试更换关键词或放宽筛选。"
        return "No matching products within budget. Try a higher budget or wider price range." if budget_applied else "No matching products. Try different keywords or wider filters."
