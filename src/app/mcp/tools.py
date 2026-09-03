"""Thin MCP tool layer: validate, route, execute, and envelope."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from ..capabilities.cart import CartCapability
from ..capabilities.chat import ChatCapability
from ..capabilities.compare import CompareCapability
from ..capabilities.search import SearchCapability
from ..config import Settings
from ..context import (
    CompareReference,
    CartItem,
    ChatMessage,
    Context,
    ErrorBody,
    ResponseEnvelope,
    SearchFilters,
    new_trace_id,
)
from ..logging import emit_log
from ..providers.cart_stub import StubCartProvider
from ..providers.cart_supabase import SupabaseCartProvider
from ..providers.catalog_remote import RemoteCatalogProvider
from ..providers.catalog_stub import StubCatalogProvider
from ..providers.llm_openai import OpenAICompatibleLLMProvider
from ..providers.safety_rules import RuleSafetyProvider


def register_tools(server, settings: Settings) -> None:
    catalog_provider = (
        RemoteCatalogProvider(settings.catalog_base_url)
        if settings.catalog_provider == "remote"
        else StubCatalogProvider()
    )
    search = SearchCapability(catalog_provider, settings.image_proxy_base)
    cart_provider = (
        SupabaseCartProvider(settings.supabase_url, settings.supabase_key, catalog_provider)
        if settings.cart_provider == "supabase"
        else StubCartProvider(settings.cart_memory)
    )
    cart = CartCapability(cart_provider)
    chat = ChatCapability(
        OpenAICompatibleLLMProvider(settings.llm_base_url, settings.llm_key, settings.llm_model),
        RuleSafetyProvider(),
        search,
        CompareCapability(catalog_provider, settings.image_proxy_base),
        cart,
    )

    @server.tool(name="symy_search", description="Search the product catalog (goods, local services, tickets) with filters. Returns structured product cards. Never adds to cart.")
    async def symy_search(
        query: str,
        context: Context,
        filters: SearchFilters | None = None,
    ) -> dict[str, Any]:
        selected = filters or SearchFilters()
        typed_context = context if isinstance(context, Context) else Context.model_validate(context)
        typed_filters = selected if isinstance(selected, SearchFilters) else SearchFilters.model_validate(selected)
        if not query or not query.strip():
            return await _invalid_input("symy_search", "query must be a non-empty string")
        return await _run("symy_search", lambda: search.execute(query, typed_filters, typed_context))

    @server.tool(name="symy_compare", description="Compare two products/services on unit price and attributes. Read-only; never modifies the cart.")
    async def symy_compare(a: CompareReference, b: CompareReference, context: Context) -> dict[str, Any]:
        compare = CompareCapability(catalog_provider, settings.image_proxy_base)
        typed_context = context if isinstance(context, Context) else Context.model_validate(context)
        typed_a = a if isinstance(a, CompareReference) else CompareReference.model_validate(a)
        typed_b = b if isinstance(b, CompareReference) else CompareReference.model_validate(b)
        return await _run("symy_compare", lambda: compare.execute(typed_a, typed_b, typed_context))

    @server.tool(name="symy_cart", description="Cart operations. Only runs when the user explicitly requested a cart action. 'add' succeeds with a budget warning if the item exceeds the budget; it never silently blocks.")
    async def symy_cart(action: str, context: Context, item: CartItem | None = None) -> dict[str, Any]:
        typed_context = context if isinstance(context, Context) else Context.model_validate(context)
        try:
            cart_item = item if isinstance(item, CartItem) else CartItem.model_validate(item or {})
        except PydanticValidationError as exc:
            return await _invalid_input("symy_cart", _validation_message(exc))
        return await _run(
            "symy_cart",
            lambda: cart.execute(action, typed_context, cart_item.product_ref, cart_item.qty),
        )

    @server.tool(name="symy_chat", description="Full shopping-conversation turn: triages intent, runs the right capability, composes a draft reply, and applies safety post-checks.")
    async def symy_chat(user_message: str, context: Context, chat_history: list[ChatMessage] | None = None) -> dict[str, Any]:
        if not user_message or not user_message.strip():
            return await _invalid_input("symy_chat", "user_message must be a non-empty string")
        typed_context = context if isinstance(context, Context) else Context.model_validate(context)
        typed_history = [
            message if isinstance(message, ChatMessage) else ChatMessage.model_validate(message)
            for message in (chat_history or [])
        ]
        return await _run("symy_chat", lambda: chat.execute(user_message, typed_context, typed_history))


async def _run(tool: str, operation) -> dict[str, Any]:
    trace_id = new_trace_id()
    started = time.perf_counter()
    try:
        data = await operation()
        envelope = ResponseEnvelope(trace_id=trace_id, ok=True, data=data)
        emit_log(trace_id=trace_id, tool=tool, latency_ms=(time.perf_counter() - started) * 1000)
        return envelope.model_dump(mode="json")
    except Exception as exc:
        code = _error_code(exc)
        message = _error_message(exc, code)
        retryable = code in {"PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE"}
        envelope = ResponseEnvelope(trace_id=trace_id, ok=False, error=ErrorBody(code=code, message=message, retryable=retryable))
        emit_log(trace_id=trace_id, tool=tool, error_code=code, latency_ms=(time.perf_counter() - started) * 1000)
        return envelope.model_dump(mode="json")


async def _invalid_input(tool: str, message: str) -> dict[str, Any]:
    trace_id = new_trace_id()
    envelope = ResponseEnvelope(
        trace_id=trace_id,
        ok=False,
        error=ErrorBody(code="INVALID_INPUT", message=message, retryable=False),
    )
    emit_log(trace_id=trace_id, tool=tool, error_code="INVALID_INPUT")
    return envelope.model_dump(mode="json")


def _error_code(exc: Exception) -> str:
    if isinstance(exc, PydanticValidationError):
        return "INVALID_INPUT"
    if isinstance(exc, TimeoutError):
        return "PROVIDER_TIMEOUT"
    if isinstance(exc, ConnectionError):
        return "PROVIDER_UNAVAILABLE"
    if isinstance(exc, LookupError):
        return exc.args[0] if exc.args and exc.args[0] in {"CART_ITEM_NOT_FOUND", "CART_EMPTY"} else "INVALID_INPUT"
    return "INTERNAL_ERROR"


def _error_message(exc: Exception, code: str) -> str:
    if isinstance(exc, LookupError) and exc.args and exc.args[0] == code:
        return " ".join(str(arg) for arg in exc.args[1:]) or code
    return str(exc) or code


def _validation_message(exc: PydanticValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid input"
    first = errors[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location} {first['msg']}" if location else str(first["msg"])
