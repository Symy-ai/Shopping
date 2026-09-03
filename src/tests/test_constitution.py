from pathlib import Path

import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.compare import CompareCapability
from app.capabilities.search import SearchCapability
from app.config import Settings
from app.context import CompareReference, Context, SearchFilters
from app.mcp.tools import register_tools
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider
from .test_units import ToolServer


@pytest.mark.asyncio
async def test_search_and_compare_never_change_cart(tmp_path: Path):
    path = tmp_path / "cart.json"
    context = Context(user_ref="constitution", session_ref="s", lang="zh", currency="CNY")
    cart = CartCapability(StubCartProvider(str(path)))

    search = await SearchCapability(StubCatalogProvider()).execute(
        "贵州酱香白酒", SearchFilters(), context
    )
    compare = await CompareCapability(StubCatalogProvider()).execute(
        CompareReference(query="贵州酱香白酒"),
        CompareReference(query="茅台镇酱酒"),
        context,
    )
    after = await cart.execute("list", context)

    assert search.cards or compare.items
    assert after.cart_lines == []
    assert after.cart_total_cents == 0


@pytest.mark.asyncio
async def test_compare_and_search_via_mcp_leave_cart_empty(tmp_path: Path):
    server = ToolServer()
    settings = Settings("stub", "", "stub", "", "", "", "", "", str(tmp_path / "cart.json"), "")
    register_tools(server, settings)
    context = {
        "user_ref": "constitution-mcp",
        "session_ref": "s",
        "lang": "zh",
        "currency": "CNY",
    }
    search = await server.tools["symy_search"]("贵州酱香白酒", context)
    compare = await server.tools["symy_compare"](
        {"product_ref": "baijiu-jiangxiang-500ml"},
        {"product_ref": "maotai-town-500ml"},
        context,
    )
    listed = await server.tools["symy_cart"]("list", context)
    assert search["ok"] and compare["ok"]
    assert listed["data"]["cart_lines"] == []
    assert listed["data"]["cart_total_cents"] == 0


@pytest.mark.asyncio
async def test_chat_via_mcp_does_not_change_cart(tmp_path: Path):
    server = ToolServer()
    settings = Settings("stub", "", "stub", "", "", "", "", "", str(tmp_path / "cart.json"), "")
    register_tools(server, settings)
    context = {
        "user_ref": "constitution-chat",
        "session_ref": "s",
        "lang": "zh",
        "currency": "CNY",
    }
    before = await server.tools["symy_cart"]("list", context)
    chat = await server.tools["symy_chat"]("帮我看看茅台镇酱酒", context)
    after = await server.tools["symy_cart"]("list", context)
    assert chat["ok"]
    assert after["data"]["cart_lines"] == before["data"]["cart_lines"] == []
    assert after["data"]["cart_total_cents"] == before["data"]["cart_total_cents"] == 0
