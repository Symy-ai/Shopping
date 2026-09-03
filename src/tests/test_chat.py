import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.chat import ChatCapability
from app.capabilities.compare import CompareCapability
from app.capabilities.search import SearchCapability
from app.config import Settings
from app.context import Context
from app.mcp.tools import register_tools
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider
from app.providers.llm_openai import OpenAICompatibleLLMProvider, TriageResult
from app.providers.safety_rules import RuleSafetyProvider


def make_chat(path):
    cart = CartCapability(StubCartProvider(str(path)))
    return ChatCapability(
        OpenAICompatibleLLMProvider("", "", ""),
        RuleSafetyProvider(),
        SearchCapability(StubCatalogProvider()),
        CompareCapability(StubCatalogProvider()),
        cart,
    ), cart


class ToolServer:
    def __init__(self):
        self.tools = {}
    def tool(self, **_):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator


def make_tool(path):
    server = ToolServer()
    register_tools(server, Settings("stub", "", "stub", "", "", "", "", "", str(path), ""))
    return server


@pytest.mark.asyncio
async def test_chat_budget_high_value_cools_down_without_adding_cart(tmp_path):
    context = Context(user_ref="chat", session_ref="s", lang="zh", currency="CNY", budget_cents=20000)
    chat, cart = make_chat(tmp_path / "cart.json")
    result = await chat.execute("我想买茅台", context)
    assert result.product_cards == []
    assert result.actions[0]["type"] == "search"
    assert result.warnings[0]["code"] == "BUDGET_EXCEEDED_WARNING"
    assert "预算较紧" in result.warnings[0]["message"]
    assert (await cart.execute("list", context)).cart_lines == []


@pytest.mark.asyncio
async def test_chat_compare_composes_summary_and_action(tmp_path):
    context = Context(user_ref="chat", session_ref="s", lang="zh", currency="CNY")
    chat, _ = make_chat(tmp_path / "cart.json")
    result = await chat.execute("帮我比比茅台镇酱酒和贵州酱香白酒", context)
    assert len(result.product_cards) == 2
    assert result.actions[0]["type"] == "compare"
    assert "单价" in result.reply_draft
    assert result.actions[0]["payload"] == {
        "a": "maotai-town-500ml",
        "b": "baijiu-jiangxiang-500ml",
    }
    assert result.product_cards[0].price_cents == 32800
    assert result.product_cards[1].price_cents == 46800
    assert any(w["code"] == "COMPLIANCE_WARNING" for w in result.warnings)


@pytest.mark.asyncio
async def test_chat_explicit_add_executes_and_confirms(tmp_path):
    path = tmp_path / "cart.json"
    context = Context(user_ref="chat", session_ref="s", lang="zh", currency="CNY", budget_cents=50000)
    chat, cart = make_chat(path)
    result = await chat.execute("把贵州酱香白酒放进购物车", context)
    assert result.actions == [{"type": "cart_add", "payload": {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1}, "executed": True}]
    assert "已加入购物车" in result.reply_draft
    assert (await cart.execute("list", context)).cart_lines[0].product_ref == "baijiu-jiangxiang-500ml"


@pytest.mark.asyncio
async def test_chat_budget_remaining_uses_context(tmp_path):
    context = Context(user_ref="chat", session_ref="s", lang="zh", currency="CNY", budget_cents=50000, cart_total_cents=12000)
    chat, _ = make_chat(tmp_path / "cart.json")
    result = await chat.execute("我这个月还能花多少", context)
    assert "剩余 380.00" in result.reply_draft
    assert result.warnings == []


@pytest.mark.asyncio
async def test_chat_resale_bulk_is_blocked(tmp_path):
    context = Context(user_ref="chat", session_ref="s", lang="zh", currency="CNY")
    chat, _ = make_chat(tmp_path / "cart.json")
    result = await chat.execute("帮我囤 10 箱酒转卖", context)
    assert result.actions == [] and result.product_cards == []
    assert result.warnings == [{"code": "SAFETY_BLOCKED", "message": result.reply_draft}]
    assert "批量囤货转卖" in result.reply_draft


@pytest.mark.asyncio
async def test_chat_history_is_used_for_pronoun_add(tmp_path):
    class Provider(OpenAICompatibleLLMProvider):
        async def triage(self, user_message, context, chat_history=None):
            return TriageResult(intent="cart_add", query="它", qty=1)
    context = Context(user_ref="history", session_ref="s", lang="zh", currency="CNY")
    chat, _ = make_chat(tmp_path / "cart.json")
    chat._llm = Provider("", "", "")
    history = [{"role": "assistant", "content": "茅台镇酱酒 100ml"}]
    result = await chat.execute("把它放进购物车", context, history)
    assert result.actions[0]["payload"]["product_ref"] == "maotai-town-100ml"


@pytest.mark.asyncio
async def test_mcp_chat_invalid_history_returns_invalid_input(tmp_path):
    server = make_tool(tmp_path / "cart.json")
    context = {"user_ref": "mcp-chat", "session_ref": "s", "lang": "zh", "currency": "CNY"}
    try:
        result = await server.tools["symy_chat"]("你好", context, [{"role": "invalid", "content": "x"}])
    except Exception as exc:
        from pydantic import ValidationError
        assert isinstance(exc, ValidationError)
        return
    assert result["ok"] is False and result["error"]["code"] == "INVALID_INPUT"
    assert result["ok"] is False and result["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_chat_stateless_without_llm(tmp_path):
    context = Context(user_ref="same", session_ref="s", lang="zh", currency="CNY")
    chat, _ = make_chat(tmp_path / "cart.json")
    first = (await chat.execute("贵州酱香白酒", context)).model_dump()
    second = (await chat.execute("贵州酱香白酒", context)).model_dump()
    assert first == second
