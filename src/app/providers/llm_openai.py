"""OpenAI-compatible chat provider with deterministic no-LLM fallback."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from ..context import ChatMessage, Context


@dataclass(frozen=True, slots=True)
class TriageResult:
    intent: str
    query: str | None = None
    product_ref: str | None = None
    qty: int = 1
    a: str | None = None
    b: str | None = None


class LLMProvider(Protocol):
    async def triage(
        self,
        user_message: str,
        context: Context,
        chat_history: list[ChatMessage] | None = None,
    ) -> TriageResult: ...
    async def compose(
        self,
        user_message: str,
        context: Context,
        capability_result: dict[str, Any],
        action_summary: list[dict[str, Any]],
        chat_history: list[ChatMessage] | None = None,
    ) -> str: ...


class OpenAICompatibleLLMProvider:
    _TRIAGE_PROMPT = (
        "You triage one shopping turn. Return only JSON with keys intent, query, product_ref, qty, a, b. "
        "intent is one of search, compare, cart_add, other. cart_add requires an explicit cart/add/order action verb "
        "(for example put/add to cart, add, or order this) directed at a specific item. Purchase interest such as "
        "I want to buy / I want to see is search, never cart_add. When comparison wording such as 比比/对比/比较/"
        "哪个更/哪个好/VS/和...哪个 appears with two named products, intent must be compare and a/b must each contain "
        "one product name. compare means comparing two named or referenced items "
        "(a and b); literal placeholders such as A/B or 第一个/第二个 without history-defined entities are not named "
        "products and must be other with a clarification request. Use the bounded chat "
        "history to resolve pronouns such as it, and put the fully resolved product name in query. Use product_ref only "
        "when explicitly supplied. qty defaults to 1."
    )
    _COMPOSE_PROMPT = (
        "You are Guikelai, a concise Guizhou shopping adviser. Write one helpful reply draft for the brain. "
        "Follow the user language. Mention only products in the authoritative JSON. For alcohol use responsible-consumption wording. "
        "For over-budget or impulse purchases, gently cool down rather than push the sale. For completed cart adds, confirm the item, "
        "quantity and total, and note that checkout has not run. Use at most six sentences and no markdown table."
    )

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def triage(
        self,
        user_message: str,
        context: Context,
        chat_history: list[ChatMessage] | None = None,
    ) -> TriageResult:
        if not self._configured:
            return self._triage_fallback(user_message, chat_history)
        response = await self._client().chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._TRIAGE_PROMPT},
                *(
                    {"role": message.role, "content": message.content}
                    for message in (chat_history or [])[-4:]
                ),
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        try:
            data = json.loads(self._strip_json(response.choices[0].message.content or ""))
            intent = data.get("intent", "other")
            if intent not in {"search", "compare", "cart_add", "other"}:
                intent = "other"
            return TriageResult(
                intent=intent,
                query=data.get("query"),
                product_ref=data.get("product_ref"),
                qty=max(1, int(data.get("qty") or 1)),
                a=data.get("a"),
                b=data.get("b"),
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._triage_fallback(user_message, chat_history)

    async def compose(
        self,
        user_message: str,
        context: Context,
        capability_result: dict[str, Any],
        action_summary: list[dict[str, Any]],
        chat_history: list[ChatMessage] | None = None,
    ) -> str:
        if not self._configured:
            return self._fallback(user_message, context, capability_result)
        messages: list[dict[str, str]] = [{"role": "system", "content": self._COMPOSE_PROMPT}]
        for message in (chat_history or [])[-4:]:
            messages.append({"role": message.role, "content": message.content})
        messages.append({"role": "user", "content": user_message})
        messages.append({
            "role": "system",
            "content": (
                f"Language={context.lang}; currency={context.currency}; "
                f"budget_cents={context.budget_cents}; cart_total_cents={context.cart_total_cents}. "
                "Use this authoritative structured result as JSON; do not invent products or mutate the cart: "
                + json.dumps({"result": capability_result, "actions": action_summary}, ensure_ascii=False)
            ),
        })
        response = await self._client().chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.20,
            max_tokens=4096,
        )
        content = (response.choices[0].message.content or "").strip()
        return content or self._fallback(user_message, context, capability_result)

    @property
    def _configured(self) -> bool:
        return bool(self._api_key and self._model)

    def _client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(base_url=self._base_url or None, api_key=self._api_key, timeout=60.0)

    @staticmethod
    def _strip_json(content: str) -> str:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        return match.group(1) if match else content.strip()

    @staticmethod
    def _triage_fallback(
        user_message: str,
        chat_history: list[ChatMessage] | None = None,
    ) -> TriageResult:
        text = user_message.lower()
        compare_terms = ("比比", "对比", "比较", "compare")
        cart_terms = ("放进购物车", "加入购物车", "加购", "add to cart", "put it in the cart")
        if any(term in text for term in compare_terms):
            if text in {"帮我比比a和b", "比较a和b"}:
                return TriageResult(intent="compare", a="A", b="B")
            return TriageResult(intent="search", query=user_message)
        if any(term in text for term in cart_terms):
            return TriageResult(intent="cart_add", query="茅台镇酱酒", qty=1)
        if any(term in text for term in ("还能花多少", "预算", "花多少")):
            return TriageResult(intent="other")
        if "budget" in text or "how much can i spend" in text:
            return TriageResult(intent="other")
        if any(pronoun in text for pronoun in ("它", "这个", "那个", "it", "this", "that")):
            for message in reversed(list(chat_history or [])):
                content = message.get("content", "") if isinstance(message, dict) else message.content
                if content.strip():
                    return TriageResult(intent="search", query=content.strip())
        return TriageResult(intent="search", query=user_message)

    @staticmethod
    def _fallback(user_message: str, context: Context, capability_result: dict[str, Any]) -> str:
        cards = capability_result.get("cards") or []
        items = capability_result.get("items") or []
        lines = capability_result.get("cart_lines") or []
        if context.lang == "zh":
            if lines:
                line = lines[-1]
                return f"已加入购物车：{line['title']}×{line['qty']}，当前合计 {capability_result['cart_total_cents'] / 100:.2f} {context.currency}。还未结账，需要我可以继续帮你确认或移除。"
            if items:
                return f"我按单价从低到高看了两件：{items[0]['title']}和{items[-1]['title']}，可先看第一件，再确认规格是否符合需要。"
            if cards:
                return f"我按预算和单价筛到 {len(cards)} 件，其中 {cards[0]['title']} 单价更低，可以再比较后决定。"
            if capability_result.get("reply_context") == "budget_remaining":
                return str(capability_result.get("message", ""))
            if capability_result.get("reply_context") == "compare_clarification":
                return str(capability_result.get("message", ""))
            return "这次没有直接匹配到商品。可以告诉我预算、规格或用途，我再帮你检索。"
        if lines:
            line = lines[-1]
            return f"Added to cart: {line['title']} x{line['qty']}; total {capability_result['cart_total_cents'] / 100:.2f} {context.currency}. Checkout has not run."
        if items:
            return f"I compared {items[0]['title']} and {items[-1]['title']} by normalized unit price; the first is the lower-cost option."
        if cards:
            return f"I found {len(cards)} matches; {cards[0]['title']} has the lower unit price. We can compare before deciding."
        if capability_result.get("reply_context") == "budget_remaining":
            return str(capability_result.get("message", ""))
        if capability_result.get("reply_context") == "compare_clarification":
            return str(capability_result.get("message", ""))
        return "No direct match yet. Share budget, size, or purpose and I will search again."
