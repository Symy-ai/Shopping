import json
from pathlib import Path

import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.compare import CompareCapability
from app.config import Settings
from app.context import CompareReference, Context
from app.mcp.tools import register_tools
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider


@pytest.fixture
def cart_path(tmp_path: Path) -> Path:
    return tmp_path / "cart.json"


@pytest.fixture
async def cart(cart_path: Path):
    capability = CartCapability(StubCartProvider(str(cart_path)))
    await capability.execute(
        "add",
        Context(user_ref="unit", session_ref="s", lang="zh", currency="CNY"),
        product_ref="baijiu-jiangxiang-500ml",
    )
    return capability


@pytest.mark.asyncio
async def test_compare_two_baijiu_orders_by_normalized_unit_price():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await CompareCapability(StubCatalogProvider(), "http://proxy").execute(
        CompareReference(product_ref="maotai-town-100ml"),
        CompareReference(product_ref="baijiu-jiangxiang-500ml"),
        context,
    )
    assert result.items[0].product_ref == "baijiu-jiangxiang-500ml"
    assert result.unit_price_delta == 195200
    assert result.verdict_hint
    assert result.notes
    assert result.items[0].image_url.startswith("http://proxy/img?")


@pytest.mark.asyncio
async def test_compare_notes_category_size_and_availability():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(query="贵州酱香白酒"),
        CompareReference(query="黄果树门票"),
        context,
    )
    assert result.items[0].category == "ticket"
    assert any("类目差异" in note for note in result.notes)
    assert any("规格不同" in note for note in result.notes)

    unavailable = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(product_ref="maotai-sold-out-500ml"),
        CompareReference(query="青岩古镇联票"),
        context,
    )
    assert unavailable.items
    assert any("已下架" in note for note in unavailable.notes)


@pytest.mark.asyncio
async def test_compare_missing_side_returns_one_sided_result():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(product_ref="maotai-town-500ml"),
        CompareReference(query="完全不存在的商品 xyzabc"),
        context,
    )
    assert [card.product_ref for card in result.items] == ["maotai-town-500ml"]
    assert result.unit_price_delta == 0
    assert any("未能找到" in note and "单边" in note for note in result.notes)


@pytest.mark.asyncio
async def test_compare_same_top_category_different_subcategory_has_note():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(query="茅台镇酱酒"),
        CompareReference(query="都匀毛尖茶"),
        context,
    )
    assert any("子类目差异" in note and "baijiu" in note and "tea" in note for note in result.notes)


@pytest.mark.asyncio
async def test_ticket_compare_keeps_service_dimensions():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(product_ref="huangguoshu-ticket"),
        CompareReference(product_ref="qingyan-ticket"),
        context,
    )
    assert all(card.category == "ticket" for card in result.items)
    assert all(card.unit_label == "/adult" for card in result.items)
    assert any("服务对比" in note for note in result.notes)


@pytest.mark.asyncio
async def test_cart_add_preserves_image_and_over_budget_succeeds_with_warning(cart_path: Path):
    context = Context(
        user_ref="over-budget",
        session_ref="s",
        lang="zh",
        currency="CNY",
        budget_cents=20000,
    )
    capability = CartCapability(StubCartProvider(str(cart_path)))
    result = await capability.execute(
        "add",
        context,
        product_ref="baijiu-jiangxiang-500ml",
        qty=1,
    )
    assert result.cart_lines[0].product_ref == "baijiu-jiangxiang-500ml"
    assert result.cart_lines[0].image_url is not None
    assert result.cart_total_cents == 32800
    assert [warning["code"] for warning in result.warnings] == ["BUDGET_EXCEEDED_WARNING"]


@pytest.mark.asyncio
async def test_cart_list_remove_and_errors(cart, cart_path: Path):
    context = Context(user_ref="unit", session_ref="s", lang="zh", currency="CNY")
    listed = await cart.execute("list", context)
    assert listed.cart_total_cents == 32800
    assert listed.cart_lines[0].image_url
    assert listed.cart_lines[0].unit_price_cents == 32800

    with pytest.raises(LookupError) as missing:
        await cart.execute("remove", context, product_ref="qingyan-ticket")
    assert missing.value.args[0] == "CART_ITEM_NOT_FOUND"

    with pytest.raises(LookupError) as empty:
        await CartCapability(StubCartProvider(str(cart_path))).execute(
            "checkout",
            Context(user_ref="empty", session_ref="s", lang="zh", currency="CNY"),
        )
    assert empty.value.args[0] == "CART_EMPTY"


@pytest.mark.asyncio
async def test_cart_list_is_price_sorted_and_checkout_returns_snapshot(cart):
    context = Context(user_ref="unit", session_ref="s", lang="zh", currency="CNY")
    await cart.execute("add", context, product_ref="tea-maojian-250g")
    result = await cart.execute("list", context)
    assert [line.price_cents for line in result.cart_lines] == [15800, 32800]
    assert [line.unit_price_cents for line in result.cart_lines] == [6320, 32800]
    checked_out = await cart.execute("checkout", context)
    assert checked_out.cart_total_cents == 48600
    assert await cart.execute("list", context) == await cart.execute("list", context)


class ToolServer:
    def __init__(self):
        self.tools = {}

    def tool(self, **_kwargs):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


@pytest.mark.asyncio
async def test_cart_domain_errors_are_enveloped(cart_path: Path):
    server = ToolServer()
    settings = Settings(
        "stub", "", "stub", "", "", "", "", "", str(cart_path), ""
    )
    register_tools(server, settings)
    context = Context(user_ref="envelope", session_ref="s", lang="zh", currency="CNY")
    add = await server.tools["symy_cart"](
        "add", context, {"product_ref": "unknown", "qty": 1}
    )
    checkout = await server.tools["symy_cart"]("checkout", context)
    assert add["error"]["code"] == "CART_ITEM_NOT_FOUND"
    assert add["error"]["message"] == "item is not in the catalog"
    assert add["error"]["retryable"] is False
    assert checkout["error"]["code"] == "CART_EMPTY"
    assert checkout["error"]["message"] == "cart is empty"
    assert checkout["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_cart_add_rejects_quantity_above_1000(cart_path: Path):
    server = ToolServer()
    settings = Settings("stub", "", "stub", "", "", "", "", "", str(cart_path), "")
    register_tools(server, settings)
    context = Context(user_ref="qty-bound", session_ref="s", lang="zh", currency="CNY")
    result = await server.tools["symy_cart"](
        "add", context, {"product_ref": "baijiu-jiangxiang-500ml", "qty": 10000000000}
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_INPUT"
    assert "less than or equal to 1000" in result["error"]["message"]
