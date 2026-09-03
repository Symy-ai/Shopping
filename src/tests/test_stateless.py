import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.compare import CompareCapability
from app.capabilities.search import SearchCapability
from app.config import Settings
from app.context import CompareReference, Context, SearchFilters
from app.mcp.tools import register_tools
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider
from app.constitution.rules import stateless_projection


@pytest.mark.asyncio
async def test_same_search_input_diffs_only_by_trace_id():
    capability = SearchCapability(StubCatalogProvider(), "http://proxy")
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    first = await capability.execute("贵州酱香白酒", SearchFilters(price_min_cents=20000), context)
    second = await capability.execute("贵州酱香白酒", SearchFilters(price_min_cents=20000), context)
    assert stateless_projection(first.model_dump(mode="json")) == stateless_projection(
        second.model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_same_enveloped_tool_input_diffs_only_by_trace_id():
    class Server:
        tools = {}

        def tool(self, **_kwargs):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

        def unused_direct_tool(self, func):
            self.tools[func.__name__] = func
            return func

    settings = Settings("stub", "", "stub", "", "", "", "", "", "", "")
    server = Server()
    register_tools(server, settings)
    context = {
        "user_ref": "u",
        "session_ref": "s",
        "lang": "zh",
        "currency": "CNY",
        "budget_cents": 20000,
    }
    first = await server.tools["symy_search"]("推荐酱酒", context)
    second = await server.tools["symy_search"]("推荐酱酒", context)
    assert stateless_projection(first) == stateless_projection(second)


@pytest.mark.asyncio
async def test_same_compare_input_diffs_only_by_trace_id():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    capability = CompareCapability(StubCatalogProvider(), "http://proxy")
    arguments = (
        CompareReference(product_ref="baijiu-jiangxiang-500ml"),
        CompareReference(product_ref="maotai-town-500ml"),
        context,
    )
    first = await capability.execute(*arguments)
    second = await capability.execute(*arguments)
    assert stateless_projection(first.model_dump(mode="json")) == stateless_projection(
        second.model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_same_cart_list_input_diffs_only_by_trace_id(tmp_path):
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    capability = CartCapability(StubCartProvider(str(tmp_path / "cart.json")))
    first = await capability.execute("list", context)
    second = await capability.execute("list", context)
    assert stateless_projection(first.model_dump(mode="json")) == stateless_projection(
        second.model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_same_chat_input_diffs_only_by_trace_id(tmp_path):
    class Server:
        tools = {}
        def tool(self, **_kwargs):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator
    settings = Settings("stub", "", "stub", "", "", "", "", "", str(tmp_path / "cart.json"), "")
    server = Server()
    register_tools(server, settings)
    context = {
        "user_ref": "chat-stateless",
        "session_ref": "s",
        "lang": "zh",
        "currency": "CNY",
    }
    history = [{"role": "assistant", "content": "茅台镇酱酒 100ml"}]
    first = await server.tools["symy_chat"]("帮我比比茅台镇酱酒和贵州酱香白酒", context, history)
    second = await server.tools["symy_chat"]("帮我比比茅台镇酱酒和贵州酱香白酒", context, history)
    assert stateless_projection(first) == stateless_projection(second)
