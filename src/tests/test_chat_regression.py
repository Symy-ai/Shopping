"""Regression: hallucinated triage product_ref must fall back to query resolution.

Case 18 of the alignment matrix ("把…放进购物车") failed end-to-end because the
triage LLM invented a product_ref; the capability must verify the ref against
the catalog before trusting it.
"""

from __future__ import annotations

import asyncio

from app.capabilities.chat import ChatCapability
from app.context import Context
from app.providers.catalog_stub import StubCatalogProvider
from app.providers.cart_stub import StubCartProvider
from app.providers.llm_openai import TriageResult
from app.providers.safety_rules import RuleSafetyProvider


class _FixedTriageLLM:
    """Mimics glm-4-flash hallucinating a product_ref that is not in the catalog."""

    async def triage(self, user_message: str, context: Context, chat_history=None) -> TriageResult:
        return TriageResult(
            intent="cart_add",
            query="茅台镇酱酒",
            product_ref="maotai_zhen_jiang_jiu",  # hallucinated slug
            qty=1,
        )

    async def compose(self, *args, **kwargs):  # pragma: no cover - trivial draft
        return "已为您加入购物车。"


def _capability(tmp_path):
    cart = StubCartProvider(str(tmp_path / "cart.json"))
    cap = ChatCapability(llm=_FixedTriageLLM(), safety=RuleSafetyProvider(), search=None, compare=None, cart=None)
    return cap, cart


def test_hallucinated_product_ref_falls_back_to_query(tmp_path, monkeypatch):
    cap, cart = _capability(tmp_path)
    ctx = Context(user_ref="regress-18", session_ref="s", lang="zh", currency="CNY")

    captured: dict = {}

    class _Cart:
        async def execute(self, action, context, reference, qty):
            captured["reference"] = reference
            captured["qty"] = qty
            return {"cart_lines": [], "cart_total_cents": 0, "warnings": []}

    class _Search:
        async def execute(self, query, filters, context):
            from app.context import ProductCard

            if query == "maotai_zhen_jiang_jiu":
                # catalog lookup for the hallucinated ref finds nothing exact
                cards = []
            else:
                cards = [ProductCard(
                    product_ref="maotai-town-500ml",
                    title="茅台镇酱酒 500ml",
                    price_cents=46800,
                    unit_price_cents=46800,
                    unit_label="/500ml",
                    currency="CNY",
                    category="goods",
                    subcategory="baijiu",
                    image_url="https://ddimg.cn/hotlink/maotai-town.jpg",
                    source="ddimg",
                    marketplace_url="https://ddimg.cn/maotai-town",
                    in_stock=True,
                )]
            class _R:
                pass
            r = _R()
            r.cards = cards
            return r

    cap._cart = _Cart()
    cap._search = _Search()

    data = asyncio.run(cap.execute("把茅台镇酱酒放进购物车", ctx, None))
    assert captured["reference"] == "maotai-town-500ml", (
        "hallucinated product_ref must not reach the cart; got "
        f"{captured['reference']}"
    )
