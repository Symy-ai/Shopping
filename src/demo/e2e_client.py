"""Call search, compare, and cart through the MCP HTTP endpoint."""

from __future__ import annotations

import argparse
import asyncio
import json

from fastmcp import Client


async def call(client: Client, tool: str, arguments: dict) -> dict:
    result = await client.call_tool(tool, arguments)
    for block in result.content:
        if getattr(block, "type", "") == "text":
            return json.loads(block.text)
    raise RuntimeError(f"{tool} returned no text content")


async def main(base_url: str) -> None:
    context = {
        "user_ref": "round2-e2e",
        "session_ref": "round2-e2e",
        "lang": "zh",
        "currency": "CNY",
    }
    cart_context = {**context, "budget_cents": 20000}
    async with Client(base_url) as client:
        outputs = {
            "search": await call(client, "symy_search", {
                "query": "贵州酱香白酒",
                "filters": {"price_min_cents": 20000, "price_max_cents": 50000},
                "context": context,
            }),
            "compare": await call(client, "symy_compare", {
                "a": {"product_ref": "maotai-town-100ml"},
                "b": {"product_ref": "baijiu-jiangxiang-500ml"},
                "context": context,
            }),
            "cart_add": await call(client, "symy_cart", {
                "action": "add",
                "context": cart_context,
                "item": {"product_ref": "baijiu-jiangxiang-500ml", "qty": 1},
            }),
            "cart_list": await call(client, "symy_cart", {
                "action": "list",
                "context": cart_context,
            }),
        }
        outputs["cart_checkout"] = await call(client, "symy_cart", {
            "action": "checkout",
            "context": cart_context,
        })
        outputs["chat"] = await call(client, "symy_chat", {
            "user_message": "帮我比比茅台镇酱酒和贵州酱香白酒",
            "chat_history": [{"role": "user", "content": "我想看贵州酱酒"}],
            "context": context,
        })
    print(json.dumps(outputs, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080/mcp/")
    args = parser.parse_args()
    asyncio.run(main(args.base_url.rstrip("/") + "/"))
