import pytest
from pydantic import ValidationError

from app.capabilities.search import SearchCapability
from app.context import Context, SearchFilters
from app.providers.catalog_stub import StubCatalogProvider


@pytest.mark.asyncio
async def test_price_filter_returns_card_with_required_fields():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await SearchCapability(StubCatalogProvider(), "http://localhost:8009").execute(
        "贵州酱香白酒", SearchFilters(price_min_cents=20000, price_max_cents=50000), context
    )
    assert result.total_hits >= 1
    card = result.cards[0]
    assert 20000 <= card.price_cents <= 50000
    assert card.image_url.startswith("http://localhost:8009/img?")
    assert card.marketplace_url.startswith("https://")
    assert card.unit_price_cents and card.unit_label


@pytest.mark.asyncio
async def test_budget_empty_result_is_friendly_degradation():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY", budget_cents=20000)
    result = await SearchCapability(StubCatalogProvider()).execute("推荐酱酒", SearchFilters(), context)
    assert result.cards == []
    assert result.total_hits == 0
    assert "预算" in result.message
    assert result.actions[0]["payload"]["query"] == "推荐酱酒"


@pytest.mark.asyncio
async def test_ticket_category_routes_to_service_card():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await SearchCapability(StubCatalogProvider()).execute(
        "黄果树门票", SearchFilters(category="ticket"), context
    )
    assert result.cards
    assert all(card.category == "ticket" for card in result.cards)
    ticket = next(card for card in result.cards if card.product_ref == "huangguoshu-ticket")
    assert ticket.subcategory == "scenic_ticket"
    assert ticket.source == "piaojia"
    assert ticket.unit_label == "/adult"


@pytest.mark.asyncio
async def test_hotlink_images_are_proxied_and_normal_images_left_alone():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await SearchCapability(StubCatalogProvider(), "http://proxy").execute(
        "黄果树门票", SearchFilters(category="ticket"), context
    )
    assert all(card.image_url.startswith("http://proxy/img?") for card in result.cards)


@pytest.mark.asyncio
async def test_search_is_unit_price_sorted_without_price_filter():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await SearchCapability(StubCatalogProvider()).execute("茅台镇酱酒", SearchFilters(), context)
    assert result.total_hits >= 2
    prices = [card.unit_price_cents for card in result.cards]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_blank_query_returns_invalid_input():
    from app.mcp.tools import register_tools
    from app.config import Settings

    class Server:
        tools = {}
        def tool(self, **_kwargs):
            def decorator(func):
                self.tools[func.__name__] = func
                return func
            return decorator

    server = Server()
    settings = Settings("stub", "", "stub", "", "", "", "", "", "", "")
    register_tools(server, settings)
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await server.tools["symy_search"](" ", context)
    assert result["ok"] is False
    assert result["error"]["code"] == "INVALID_INPUT"
    assert result["error"]["retryable"] is False


def test_invalid_category_is_rejected_before_execution():
    with pytest.raises(ValidationError):
        SearchFilters(category="invalid")


@pytest.mark.asyncio
async def test_normal_image_is_left_unchanged():
    context = Context(user_ref="u", session_ref="s", lang="zh", currency="CNY")
    result = await SearchCapability(StubCatalogProvider(), "http://proxy").execute(
        "都匀毛尖绿茶", SearchFilters(), context
    )
    assert result.cards
    assert all(card.image_url.startswith("http://proxy/img?") for card in result.cards)
