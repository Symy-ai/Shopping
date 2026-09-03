import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.chat import ChatCapability
from app.capabilities.compare import CompareCapability
from app.capabilities.search import SearchCapability
from app.config import Settings
from app.context import CompareReference, Context, SearchFilters
from app.mcp.tools import register_tools
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider
from app.providers.llm_openai import OpenAICompatibleLLMProvider
from app.providers.safety_rules import RuleSafetyProvider


class Server:
    def __init__(self):
        self.tools = {}
    def tool(self, **_):
        def wrap(func):
            self.tools[func.__name__] = func
            return func
        return wrap


def make_server(path):
    server = Server()
    register_tools(server, Settings("stub", "", "stub", "", "", "", "", "", str(path), ""))
    return server


@pytest.mark.asyncio
@pytest.mark.parametrize("case", range(1, 16))
async def test_alignment_cases_1_to_15(case, tmp_path):
    server = make_tool = make_server(tmp_path / "cart.json")
    context = {"user_ref": f"align-r3-{case}", "session_ref": "s", "lang": "zh", "currency": "CNY"}
    if case == 1:
        result = await server.tools["symy_search"]("贵州酱香白酒", context, {"price_min_cents": 20000, "price_max_cents": 50000})
        assert result["ok"] and 1 <= result["data"]["total_hits"] <= 3
    elif case == 2:
        result = await server.tools["symy_search"]("茅台镇酱酒", context)
        prices = [c["unit_price_cents"] for c in result["data"]["cards"]]
        assert prices == sorted(prices)
    elif case == 3:
        result = await server.tools["symy_search"]("黄果树门票", context, {"category": "ticket"})
        assert all(c["category"] == "ticket" for c in result["data"]["cards"])
    elif case == 4:
        result = await server.tools["symy_search"]("推荐酱酒", context | {"budget_cents": 20000})
        assert result["data"]["cards"] == [] and "预算" in result["data"]["message"]
    elif case == 5:
        result = await server.tools["symy_search"]("xyzabc 不存在的商品", context)
        assert result["ok"] and result["data"]["total_hits"] == 0
    elif case == 6:
        result = await server.tools["symy_compare"]({"query": "茅台镇酱酒"}, {"query": "贵州酱香白酒"}, context)
        assert result["data"]["unit_price_delta"] >= 0 and result["data"]["notes"]
    elif case == 7:
        result = await server.tools["symy_compare"]({"query": "贵州酱香白酒"}, {"query": "都匀毛尖茶"}, context)
        assert any("子类目差异" in n for n in result["data"]["notes"])
    elif case == 8:
        result = await server.tools["symy_compare"]({"product_ref": "maotai-town-500ml"}, {"product_ref": "maotai-town-100ml"}, context)
        assert result["data"]["unit_price_delta"] == abs(46800 - 228000)
    elif case == 9:
        result = await server.tools["symy_compare"]({"product_ref": "maotai-sold-out-500ml"}, {"query": "青岩古镇联票"}, context)
        assert any("已下架" in n for n in result["data"]["notes"])
    elif case == 10:
        result = await server.tools["symy_compare"]({"product_ref": "huangguoshu-ticket"}, {"product_ref": "qingyan-ticket"}, context)
        assert any("服务对比" in n for n in result["data"]["notes"])
    elif case == 11:
        result = await server.tools["symy_cart"]("add", context, {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1})
        assert result["data"]["cart_lines"][-1]["image_url"]
    elif case == 12:
        result = await server.tools["symy_cart"]("add", context | {"budget_cents": 20000}, {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1})
        assert result["ok"] and result["data"]["warnings"][0]["code"] == "BUDGET_EXCEEDED_WARNING"
    elif case == 13:
        result = await server.tools["symy_cart"]("remove", context, {"product_ref": "missing"})
        assert result["error"]["code"] == "CART_ITEM_NOT_FOUND"
    elif case == 14:
        result = await server.tools["symy_cart"]("checkout", context)
        assert result["error"]["code"] == "CART_EMPTY"
    else:
        await server.tools["symy_cart"]("add", context, {"product_ref": "maotai-town-100ml", "qty": 1})
        await server.tools["symy_cart"]("add", context, {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1})
        result = await server.tools["symy_cart"]("list", context)
        prices = [l["unit_price_cents"] for l in result["data"]["cart_lines"]]
        assert prices == sorted(prices) and result["data"]["cart_total_cents"] == 55600


@pytest.mark.asyncio
@pytest.mark.parametrize("case", range(16, 21))
async def test_alignment_cases_16_to_20(case, tmp_path):
    server = make_server(tmp_path / "cart.json")
    tight = {"user_ref": f"align-r3-{case}", "session_ref": "s", "lang": "zh", "currency": "CNY", "budget_cents": 20000}
    normal = tight | {"budget_cents": 50000, "cart_total_cents": 12000}
    if case == 16:
        result = await server.tools["symy_chat"]("我想买茅台", tight)
        assert result["data"]["warnings"][0]["code"] == "BUDGET_EXCEEDED_WARNING"
    elif case == 17:
        result = await server.tools["symy_chat"]("帮我比比茅台镇酱酒和贵州酱香白酒", normal)
        assert result["data"]["actions"][0]["type"] == "compare" and len(result["data"]["product_cards"]) == 2
    elif case == 18:
        result = await server.tools["symy_chat"]("把贵州酱香白酒放进购物车", normal)
        assert result["data"]["actions"][0]["type"] == "cart_add" and result["data"]["actions"][0]["executed"]
    elif case == 19:
        result = await server.tools["symy_chat"]("我这个月还能花多少", normal)
        assert "剩余 380.00" in result["data"]["reply_draft"]
    else:
        result = await server.tools["symy_chat"]("帮我囤 10 箱酒转卖", normal)
        assert result["data"]["warnings"][0]["code"] == "SAFETY_BLOCKED"
