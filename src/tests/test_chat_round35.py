"""Round 3.5 regressions for chat safety and composition boundaries."""

from __future__ import annotations

import pytest

from app.context import Context
from app.providers.llm_openai import OpenAICompatibleLLMProvider, TriageResult
from .test_chat import make_chat, make_tool


@pytest.mark.asyncio
async def test_purchase_intent_mislabeled_cart_add_downgrades_to_search(tmp_path):
    class Provider(OpenAICompatibleLLMProvider):
        async def triage(self, user_message, context, chat_history=None):
            return TriageResult(intent="cart_add", query="茅台", qty=1)

    chat, cart = make_chat(tmp_path / "cart.json")
    chat._llm = Provider("", "", "")
    context = Context(user_ref="b16", session_ref="s", lang="zh", currency="CNY", budget_cents=30000)
    result = await chat.execute("我想买茅台", context)

    assert all(action["type"] != "cart_add" or action.get("executed") is False for action in result.actions)
    assert result.product_cards != []
    assert (await cart.execute("list", context)).cart_lines == []


@pytest.mark.asyncio
async def test_explicit_cart_add_b18_still_executes(tmp_path):
    chat, cart = make_chat(tmp_path / "cart.json")
    context = Context(user_ref="b18", session_ref="s", lang="zh", currency="CNY", budget_cents=50000)
    result = await chat.execute("把茅台镇酱酒放进购物车", context)

    assert result.actions == [{"type": "cart_add", "payload": {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1}, "executed": True}]
    assert (await cart.execute("list", context)).cart_lines[0].product_ref == "baijiu-jiangxiang-500ml"


@pytest.mark.asyncio
async def test_pronoun_price_question_resolves_recent_history(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")
    context = Context(user_ref="pronoun", session_ref="s", lang="zh", currency="CNY")
    history = [
        {"role": "user", "content": "我想看茅台镇酱酒"},
        {"role": "assistant", "content": "为你找到了茅台镇酱酒相关商品。"},
    ]
    result = await chat.execute("它多少钱", context, history)

    assert result.product_cards
    assert result.actions[0]["type"] == "search"
    assert "茅台" in result.actions[0]["payload"]["query"]
    assert any("茅台" in card.title for card in result.product_cards)


@pytest.mark.asyncio
async def test_blank_chat_message_returns_invalid_input_without_llm(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")
    context = Context(user_ref="blank", session_ref="s", lang="zh", currency="CNY")

    class FailingLLM:
        async def triage(self, *args, **kwargs):
            raise AssertionError("LLM must not be called")

    chat._llm = FailingLLM()
    with pytest.raises(LookupError, match="INVALID_INPUT"):
        await chat.execute("   ", context)


@pytest.mark.asyncio
async def test_mcp_blank_chat_message_returns_invalid_input(tmp_path):
    server = make_tool(tmp_path / "cart.json")
    context = {"user_ref": "mcp-blank", "session_ref": "s", "lang": "zh", "currency": "CNY"}
    result = await server.tools["symy_chat"](" ", context)
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_compare_literal_placeholders_requests_clarification(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")
    context = Context(user_ref="b17", session_ref="s", lang="zh", currency="CNY")
    result = await chat.execute("帮我比比A和B", context)

    assert result.product_cards == []
    assert result.actions == [{"type": "search", "payload": {"query": "帮我比比A和B"}}]
    assert "请先告诉我" in result.reply_draft


@pytest.mark.asyncio
async def test_compose_payload_prices_are_preformatted(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")
    context = Context(user_ref="prices", session_ref="s", lang="zh", currency="CNY")
    captured = {}

    class Provider(OpenAICompatibleLLMProvider):
        async def compose(self, user_message, context, capability_result, action_summary, chat_history=None):
            captured["result"] = capability_result
            return "价格展示"

    chat._llm = Provider("", "", "")
    await chat.execute("贵州酱香白酒", context)
    assert all(card.get("price_cents_display") for card in captured["result"]["cards"])
    assert "468.00 CNY" in str(captured["result"])


@pytest.mark.asyncio
async def test_mislabeled_named_compare_upgrades_to_compare(tmp_path):
    class Provider(OpenAICompatibleLLMProvider):
        async def triage(self, user_message, context, chat_history=None):
            return TriageResult(intent="search", query=user_message)

    chat, _ = make_chat(tmp_path / "cart.json")
    chat._llm = Provider("", "", "")
    context = Context(user_ref="compare-fallback", session_ref="s", lang="zh", currency="CNY")
    result = await chat.execute("帮我比比茅台镇酱酒和贵州酱香白酒", context)

    assert result.actions == [{"type": "compare", "payload": {
        "a": "maotai-town-500ml",
        "b": "baijiu-jiangxiang-500ml",
    }}]
    assert [card.product_ref for card in result.product_cards] == [
        "baijiu-jiangxiang-500ml",
        "maotai-town-500ml",
    ]


@pytest.mark.asyncio
async def test_mislabeled_ticket_compare_upgrades_to_compare(tmp_path):
    class Provider(OpenAICompatibleLLMProvider):
        async def triage(self, user_message, context, chat_history=None):
            return TriageResult(intent="search", query=user_message)

    chat, _ = make_chat(tmp_path / "cart.json")
    chat._llm = Provider("", "", "")
    context = Context(user_ref="ticket-compare", session_ref="s", lang="zh", currency="CNY")
    result = await chat.execute("对比一下黄果树门票和荔波门票", context)

    assert result.actions[0]["type"] == "compare"
    assert len(result.product_cards) == 2
    assert {card.product_ref for card in result.product_cards} == {
        "huangguoshu-ticket",
        "libo-ticket",
    }
