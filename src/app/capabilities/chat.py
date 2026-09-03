"""One-turn chat capability: triage, execute, compose, post-check."""

from __future__ import annotations

import re
from typing import Any

from ..context import ChatData, ChatMessage, CompareReference, Context, ProductCard, SearchFilters
from .cart import CartCapability
from .compare import CompareCapability
from .search import SearchCapability
from ..providers.llm_openai import LLMProvider, TriageResult
from ..providers.safety_rules import SafetyProvider


class ChatCapability:
    _pronoun_ref = "maotai-town-100ml"
    _compare_keywords = re.compile(r"比比|对比|比较|哪个更|哪个好|vs", re.IGNORECASE)
    _compare_split = re.compile(r"\s*(?:和|跟|与|vs\.?|VS\.?)\s*", re.IGNORECASE)

    def __init__(
        self,
        llm: LLMProvider,
        safety: SafetyProvider,
        search: SearchCapability,
        compare: CompareCapability,
        cart: CartCapability,
    ) -> None:
        self._llm = llm
        self._safety = safety
        self._search = search
        self._compare = compare
        self._cart = cart

    async def execute(
        self,
        user_message: str,
        context: Context,
        chat_history: list[ChatMessage] | None = None,
    ) -> ChatData:
        if not user_message or not user_message.strip():
            raise LookupError("INVALID_INPUT", "user_message must be a non-empty string")
        safety = self._safety.check(user_message, context)
        if safety.blocked:
            return ChatData(
                reply_draft=safety.message,
                product_cards=[],
                actions=[],
                warnings=[{"code": "SAFETY_BLOCKED", "message": safety.message}],
            )

        triage = await self._llm.triage(user_message, context, chat_history)
        result: Any
        actions: list[dict[str, Any]] = []
        warnings: list[dict[str, str]] = []
        upgrade = (
            await self._compare_fallback(user_message, context)
            if triage.intent == "search" and self._compare_keywords.search(user_message)
            else None
        )
        if upgrade is not None:
            triage = upgrade
        if triage.intent == "search":
            query = triage.query or user_message
            result = await self._search.execute(
                query,
                SearchFilters(),
                context,
            )
            actions = [{"type": "search", "payload": {"query": query}}]
        elif triage.intent == "compare":
            left = triage.product_ref if triage.product_ref and triage.a is None else triage.a
            right = triage.b
            if self._compare_needs_clarification(left, right, chat_history):
                result = {
                    "reply_context": "compare_clarification",
                    "message": (
                        "请先告诉我要比较的两件商品，例如“比较茅台镇酱酒和贵州酱香白酒”。"
                        if context.lang == "zh"
                        else "Tell me which two items to compare, for example 'compare Maotai-town sauce baijiu and Guizhou sauce-flavor baijiu'."
                    ),
                    "warnings": [],
                }
                actions = [{"type": "search", "payload": {"query": user_message}}]
                payload = result
                draft = await self._llm.compose(user_message, context, payload, actions, chat_history)
                return ChatData(reply_draft=draft, product_cards=[], actions=actions, warnings=warnings)
            result = await self._compare.execute(self._reference(left), self._reference(right), context)
            actions = [{"type": "compare", "payload": {"a": left, "b": right}}]
        elif triage.intent == "cart_add":
            if not self._has_explicit_add_action(user_message):
                query = triage.query or user_message
                result = await self._search.execute(query, SearchFilters(), context)
                payload = result if isinstance(result, dict) else result.model_dump(mode="json")
                cards = payload.get("cards") or []
                draft = await self._llm.compose(user_message, context, self._format_prices(payload), actions, chat_history)
                warnings.extend(self._postcheck(user_message, context, payload, cards))
                if safety.message:
                    warnings.insert(0, {"code": "BUDGET_EXCEEDED_WARNING", "message": safety.message})
                return ChatData(
                    reply_draft=draft,
                    product_cards=cards,
                    actions=[{"type": "search", "payload": {"query": query}, "executed": False}],
                    warnings=warnings,
                )
            # Triage LLMs may hallucinate product_refs (transliterated slugs or
            # raw titles). Trust product_ref only when it exists in the catalog;
            # otherwise fall back to query resolution.
            reference = None
            if triage.product_ref and await self._catalog_has(triage.product_ref):
                reference = triage.product_ref
            reference = reference or await self._resolve_query(triage.query or user_message)
            result = await self._cart.execute("add", context, reference, triage.qty)
            actions = [{"type": "cart_add", "payload": {"product_ref": reference, "qty": triage.qty}, "executed": True}]
        else:
            result = await self._budget_reply(user_message, context)
            actions = []

        payload = result if isinstance(result, dict) else result.model_dump(mode="json")
        cards = payload.get("cards") or payload.get("items") or []
        draft = await self._llm.compose(user_message, context, self._format_prices(payload), actions, chat_history)
        warnings.extend(self._postcheck(user_message, context, payload, cards))
        if safety.message:
            warnings.insert(0, {
                "code": "BUDGET_EXCEEDED_WARNING",
                "message": safety.message,
            })
        return ChatData(reply_draft=draft, product_cards=cards, actions=actions, warnings=warnings)

    async def _budget_reply(self, user_message: str, context: Context) -> ChatData:
        zh = context.lang == "zh"
        budget = context.budget_cents
        cart_total = context.cart_total_cents or 0
        if budget is None:
            message = "目前没有传入可用的月度预算。可以告诉我预算，我会按剩余额度帮你参考。" if zh else "No monthly budget was provided. Share one and I will use remaining budget as a guide."
        else:
            remaining = budget - cart_total
            message = (
                f"本月预算 {budget / 100:.2f} {context.currency}，购物车已用 {cart_total / 100:.2f}，剩余 {remaining / 100:.2f}。"
                if zh else f"Monthly budget {budget / 100:.2f} {context.currency}; cart uses {cart_total / 100:.2f}, leaving {remaining / 100:.2f}."
            )
        return {
            "reply_context": "budget_remaining",
            "message": message,
            "warnings": [] if budget is None or budget - cart_total >= 0 else [{
                "code": "BUDGET_EXCEEDED_WARNING",
                "message": (
                    f"购物车总额 {cart_total / 100:.2f} {context.currency}，超出预算 {budget / 100:.2f}。"
                    if zh
                    else f"Cart total {cart_total / 100:.2f} {context.currency} exceeds budget {budget / 100:.2f} {context.currency}."
                ),
            }],
        }

    async def _compare_fallback(self, user_message: str, context: Context) -> TriageResult | None:
        text = re.sub(
            r"^(?:请|帮忙?|帮我)?(?:我)?(?:对比|比较|比比)一下?",
            "",
            user_message.strip(),
        )
        text = re.sub(r"^(?:帮忙?|帮我)?(?:比比|对比|比较)", "", text.strip())
        parts = [part.strip() for part in self._compare_split.split(text) if part.strip()]
        if len(parts) != 2:
            return None
        resolved: list[str] = []
        for part in parts:
            query = self._compare_keywords.sub("", part).strip()
            if not query:
                return None
            is_ticket = "门票" in query
            result = await self._search.execute(
                query,
                SearchFilters(category="ticket" if is_ticket else None),
                context,
            )
            if not result.cards:
                return None
            base_query = query.removesuffix("门票")
            subcategory = "scenic_ticket" if is_ticket else None
            candidates = [
                card for card in result.cards
                if not is_ticket or (card.category == "ticket" and card.subcategory == subcategory)
            ]
            exact = (
                next((card for card in candidates if card.title.startswith(base_query)), None)
                or next((card for card in candidates if base_query in card.title), None)
            )
            preferred = exact or next(
                (card for card in candidates if query in card.title),
                candidates[0] if candidates else result.cards[0],
            )
            resolved.append(preferred.product_ref)
        return TriageResult(intent="compare", a=resolved[0], b=resolved[1])

    @staticmethod
    def _has_explicit_add_action(user_message: str) -> bool:
        normalized = "".join(user_message.split()).lower()
        return any(term in normalized for term in (
            "放购物车", "放进购物车", "放入购物车", "加入购物车", "加购", "买这个", "来一", "下单",
            "addtocart", "putitinthecart", "putitinthe cart", "addtocart",
        ))

    @staticmethod
    def _compare_needs_clarification(
        left: str,
        right: str,
        chat_history: list[ChatMessage] | None,
    ) -> bool:
        if ChatCapability._last_product(chat_history):
            return False
        return any(value.strip().lower() in {"a", "b", "第一个", "第二个", "1", "2"} for value in (left, right))

    @staticmethod
    def _format_prices(payload: dict[str, Any]) -> dict[str, Any]:
        composed = {key: ([dict(item) for item in value] if key in {"cards", "items", "cart_lines"} and isinstance(value, list) else value) for key, value in payload.items()}
        for collection_name in ("cards", "items", "cart_lines"):
            for item in composed.get(collection_name) or []:
                if not isinstance(item, dict):
                    continue
                for field_name in ("price_cents", "unit_price_cents"):
                    cents = item.get(field_name)
                    if isinstance(cents, int):
                        item[f"{field_name}_display"] = f"{cents / 100:.2f} {item.get('currency', 'CNY')}"
        return composed

    async def _catalog_has(self, product_ref: str) -> bool:
        """Best-effort catalog existence check for a product_ref."""
        try:
            result = await self._search.execute(product_ref, SearchFilters(), Context(
                user_ref="chat-resolver", session_ref="chat-resolver", lang="zh", currency="CNY"
            ))
            return any(card.product_ref == product_ref for card in result.cards)
        except Exception:
            return False

    async def _resolve_query(self, query: str) -> str:
        if query in {"它", "这个", "那个", "it", "this", "that"}:
            return self._pronoun_ref
        result = await self._search.execute(query, SearchFilters(), Context(
            user_ref="chat-resolver", session_ref="chat-resolver", lang="zh", currency="CNY"
        ))
        if result.cards:
            return result.cards[0].product_ref
        raise LookupError("CART_ITEM_NOT_FOUND", "chat could not resolve the item to add")

    @staticmethod
    def _reference(value: str | None) -> CompareReference:
        if value and value.startswith("product:"):
            return CompareReference(product_ref=value.split(":", 1)[1])
        if value and value in {"maotai-town-500ml", "baijiu-jiangxiang-500ml", "huangguoshu-ticket", "libo-ticket", "qingyan-ticket"}:
            return CompareReference(product_ref=value)
        return CompareReference(query=value or "")

    @staticmethod
    def _last_product(history: list[ChatMessage] | None, skip_last: bool = False) -> str | None:
        messages = list(history or [])
        if skip_last:
            messages = messages[:-1]
        for message in reversed(messages):
            if message.role == "assistant" or "茅台" in message.content or "酱酒" in message.content:
                return message.content
        return None

    def _postcheck(
        self,
        user_message: str,
        context: Context,
        payload: dict[str, Any],
        cards: list[ProductCard],
    ) -> list[dict[str, str]]:
        warnings: list[dict[str, str]] = []
        if any(card.get("compliance") for card in cards if isinstance(card, dict)):
            warning = "涉及酒类等受控商品，请遵守当地法规并理性消费。" if context.lang == "zh" else "This includes regulated alcohol; follow local law and consume responsibly."
            warnings.append({"code": "COMPLIANCE_WARNING", "message": warning})
        if payload.get("warnings"):
            warnings.extend(payload["warnings"])
        if context.budget_cents is not None and cards and min(card["price_cents"] for card in cards if isinstance(card, dict)) > context.budget_cents:
            warning = "预算较紧，建议先比较单价或选择小规格；如果现在确实需要，也由你决定。" if context.lang == "zh" else "Budget is tight; compare unit prices or choose a smaller size first if this is not the right time."
            warnings.append({"code": "BUDGET_EXCEEDED_WARNING", "message": warning})
        return warnings
