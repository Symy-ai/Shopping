"""Constitution rule 6 (compliance warnings) and rule 7 (language follows context.lang).

Pins the previously untested English paths: every user-facing string must follow
context.lang, and compliance-bearing (alcohol) results must carry a warning in
both languages.
"""

import re

import pytest

from app.capabilities.cart import CartCapability
from app.capabilities.chat import ChatCapability
from app.capabilities.compare import CompareCapability
from app.capabilities.search import SearchCapability
from app.context import CompareReference, Context, SearchFilters
from app.providers.cart_stub import StubCartProvider
from app.providers.catalog_stub import StubCatalogProvider
from app.providers.llm_openai import OpenAICompatibleLLMProvider
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


def _no_cjk(*texts: str) -> bool:
    return not any(re.search(r"[\u4e00-\u9fff]", text) for text in texts if text)


@pytest.mark.asyncio
async def test_rule7_chat_compare_clarification_follows_lang(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")

    zh = Context(user_ref="i18n", session_ref="s", lang="zh", currency="CNY")
    zh_result = await chat.execute("比较a和b", zh)
    assert "请先告诉我要比较的两件商品" in zh_result.reply_draft

    en = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY")
    en_result = await chat.execute("比较a和b", en)
    assert "Tell me which two items to compare" in en_result.reply_draft
    assert _no_cjk(en_result.reply_draft)


@pytest.mark.asyncio
async def test_rule7_chat_budget_warning_follows_lang(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")

    zh = Context(user_ref="i18n", session_ref="s", lang="zh", currency="CNY", budget_cents=50000, cart_total_cents=120000)
    zh_result = await chat.execute("我这个月还能花多少", zh)
    zh_warning = next(w for w in zh_result.warnings if w["code"] == "BUDGET_EXCEEDED_WARNING")
    assert "超出预算" in zh_warning["message"]

    en = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY", budget_cents=50000, cart_total_cents=120000)
    en_result = await chat.execute("how much can i spend", en)
    assert "leaving 500.00" in en_result.reply_draft or "500.00" in en_result.reply_draft
    en_warning = next(w for w in en_result.warnings if w["code"] == "BUDGET_EXCEEDED_WARNING")
    assert "exceeds budget" in en_warning["message"]
    assert _no_cjk(en_warning["message"])


@pytest.mark.asyncio
async def test_rule7_search_empty_message_follows_lang():
    search = SearchCapability(StubCatalogProvider())
    filters = SearchFilters()

    zh = Context(user_ref="i18n", session_ref="s", lang="zh", currency="CNY", budget_cents=20000)
    zh_result = await search.execute("完全不存在的商品 xyzabc", filters, zh)
    assert "预算范围内暂无匹配商品" in (zh_result.message or "")

    en = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY", budget_cents=20000)
    en_result = await search.execute("完全不存在的商品 xyzabc", filters, en)
    assert "No matching products within budget" in (en_result.message or "")
    assert _no_cjk(en_result.message or "")


@pytest.mark.asyncio
async def test_rule6_compare_compliance_note_and_verdict_follow_lang():
    compare = CompareCapability(StubCatalogProvider())
    context = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY")

    result = await compare.execute(
        CompareReference(product_ref="maotai-town-100ml"),
        CompareReference(product_ref="baijiu-jiangxiang-500ml"),
        context,
    )
    assert result.verdict_hint == "The first item has the lower unit price."
    assert any("alcohol" in note for note in result.notes)
    assert all(_no_cjk(note) for note in result.notes)


@pytest.mark.asyncio
async def test_rule6_chat_compliance_warning_follows_lang(tmp_path):
    chat, _ = make_chat(tmp_path / "cart.json")

    zh = Context(user_ref="i18n", session_ref="s", lang="zh", currency="CNY")
    zh_result = await chat.execute("贵州酱香白酒", zh)
    zh_warning = next(w for w in zh_result.warnings if w["code"] == "COMPLIANCE_WARNING")
    assert "涉及酒类等受控商品" in zh_warning["message"]

    en = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY")
    en_result = await chat.execute("贵州酱香白酒", en)
    en_warning = next(w for w in en_result.warnings if w["code"] == "COMPLIANCE_WARNING")
    assert "regulated alcohol" in en_warning["message"]
    assert _no_cjk(en_warning["message"])


@pytest.mark.asyncio
async def test_rule7_cart_budget_warning_follows_lang(tmp_path):
    cart = CartCapability(StubCartProvider(str(tmp_path / "cart.json")))

    zh = Context(user_ref="i18n", session_ref="s", lang="zh", currency="CNY", budget_cents=20000)
    zh_result = await cart.execute("add", zh, product_ref="baijiu-jiangxiang-500ml", qty=1)
    assert zh_result.warnings[0]["code"] == "BUDGET_EXCEEDED_WARNING"
    assert "超出预算" in zh_result.warnings[0]["message"]

    en_cart = CartCapability(StubCartProvider(str(tmp_path / "cart-en.json")))
    en = Context(user_ref="i18n", session_ref="s", lang="en", currency="CNY", budget_cents=20000)
    en_result = await en_cart.execute("add", en, product_ref="baijiu-jiangxiang-500ml", qty=1)
    assert en_result.warnings[0]["code"] == "BUDGET_EXCEEDED_WARNING"
    assert "exceeds budget" in en_result.warnings[0]["message"]
    assert _no_cjk(en_result.warnings[0]["message"])
