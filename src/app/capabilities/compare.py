"""Read-only product comparison capability."""

from __future__ import annotations

from ..context import CompareData, CompareReference, Context, ProductCard
from ..constitution.rules import apply_image_proxy
from ..providers.catalog_stub import CatalogItem, CatalogProvider


class CompareCapability:
    def __init__(self, provider: CatalogProvider, image_proxy_base: str = "") -> None:
        self._provider = provider
        self._image_proxy_base = image_proxy_base

    async def execute(self, a: CompareReference, b: CompareReference, context: Context) -> CompareData:
        first = await self._try_resolve(a)
        second = await self._try_resolve(b)
        missing = [
            reference.query or reference.product_ref or "unknown item"
            for reference, resolved in ((a, first), (b, second))
            if resolved is None
        ]
        resolved = [item for item in (first, second) if item is not None]
        if not resolved:
            raise LookupError("CART_ITEM_NOT_FOUND", "no compare side could be resolved")
        first = resolved[0]
        second = resolved[1] if len(resolved) == 2 else resolved[0]
        if len(resolved) == 2 and first.product_ref == second.product_ref:
            missing = [resolved[0].title]
            notes = self._missing_notes(missing, context.lang)
            return CompareData(
                items=[self._card(first)],
                unit_price_delta=0,
                verdict_hint=self._verdict(context.lang),
                notes=notes,
            )
        ordered = sorted(
            resolved,
            key=lambda item: (
                item.unit_price_cents if item.unit_price_cents is not None else item.price_cents,
                item.product_ref,
            ),
        )
        cards = apply_image_proxy([self._card(item) for item in ordered], self._image_proxy_base)
        return CompareData(
            items=cards,
            unit_price_delta=self._delta(cards),
            verdict_hint=self._verdict(context.lang),
            notes=self._missing_notes(missing, context.lang) + self._notes(first, second, context.lang),
        )

    async def _try_resolve(self, reference: CompareReference) -> CatalogItem | None:
        if reference.product_ref is not None:
            matches = [
                item
                for item in await self._provider.search("", category=None)
                if item.product_ref == reference.product_ref
            ]
        else:
            matches = await self._provider.search(reference.query or "", category=None)
            query = reference.query or ""
            matches = (
                [item for item in matches if item.title.startswith(query)]
                or [item for item in matches if query in item.title]
                or matches
            )
        return matches[0] if matches else None

    def _card(self, item: CatalogItem) -> ProductCard:
        return ProductCard(
            product_ref=item.product_ref,
            title=item.title,
            price_cents=item.price_cents,
            unit_price_cents=item.unit_price_cents or item.price_cents,
            unit_label=item.unit_label,
            currency=item.currency,
            category=item.category,
            subcategory=item.subcategory,
            image_url=item.image_url,
            source=item.source,
            marketplace_url=item.marketplace_url,
            in_stock=item.in_stock,
            compliance=item.compliance,
        )

    def _delta(self, cards: list[ProductCard]) -> int:
        prices = [card.unit_price_cents or card.price_cents for card in cards]
        return abs(prices[0] - prices[-1])

    def _verdict(self, lang: str) -> str:
        return "单价更低者排前，优先考虑第一项。" if lang == "zh" else "The first item has the lower unit price."

    def _notes(self, first: CatalogItem, second: CatalogItem, lang: str) -> list[str]:
        notes: list[str] = []
        unavailable = [item for item in (first, second) if not item.in_stock]
        if unavailable:
            names = "、".join(item.title for item in unavailable)
            notes.append(
                f"警告：{names}已下架或无货，仅能比较单边信息。"
                if lang == "zh"
                else f"Warning: {names} is unavailable; only one side can be purchased."
            )
        if first.category != second.category:
            notes.append(
                f"类目差异：{first.category} vs {second.category}，单价口径可能不完全等价。"
                if lang == "zh"
                else f"Category difference: {first.category} vs {second.category}; unit prices may not be fully equivalent."
            )
        if first.category == second.category and first.subcategory != second.subcategory:
            notes.append(
                f"子类目差异：{first.subcategory} vs {second.subcategory}，不属于同类可比商品。"
                if lang == "zh"
                else f"Subcategory difference: {first.subcategory} vs {second.subcategory}; they are not directly comparable."
            )
        if first.unit_label != second.unit_label:
            notes.append(
                f"规格不同：{first.unit_label or '未标注'} vs {second.unit_label or '未标注'}，已按单价归一化。"
                if lang == "zh"
                else f"Different sizes: {first.unit_label or 'unlabeled'} vs {second.unit_label or 'unlabeled'}; unit prices are normalized."
            )
        if first.category == "ticket" and second.category == "ticket":
            notes.append(
                "服务对比需同时考虑包含项目、开放时长和使用条件。"
                if lang == "zh"
                else "Ticket comparison should also consider inclusions, duration, and redemption conditions."
            )
        if any(item.compliance for item in (first, second)):
            notes.append(
                "涉及酒类等受控商品，请遵守当地法规并理性消费。"
                if lang == "zh"
                else "This includes a controlled category such as alcohol; comply with local laws and consume responsibly."
            )
        return notes

    def _missing_notes(self, missing: list[str], lang: str) -> list[str]:
        if not missing:
            return []
        names = "、".join(missing)
        return [
            f"警告：{names} 未能找到，仅能比较单边信息。"
            if lang == "zh"
            else f"Warning: {names} could not be found; only one side is available for comparison."
        ]
