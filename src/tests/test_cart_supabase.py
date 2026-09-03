import json as jsonlib

import httpx
import pytest

from app.providers.cart_supabase import SupabaseCartProvider
from app.providers.catalog_stub import StubCatalogProvider


class FakeTransport:
    def __init__(self, lines: dict[str, list[dict]]) -> None:
        self.lines = lines
        self.requests: list[tuple[str, str, dict | None, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        method = request.method
        url = str(request.url)
        json = None
        if request.content:
            json = jsonlib.loads(request.content)
        headers = dict(request.headers)
        self.requests.append((method, url, json, headers))
        if method == "GET":
            rows = self.lines.get("user", [])
            return httpx.Response(200, json=rows)
        if method == "POST":
            rows = self.lines.setdefault("user", [])
            row = next(
                (entry for entry in rows if entry["product_ref"] == json["product_ref"]),
                None,
            )
            if row:
                row.update({key: value for key, value in json.items() if key != "user_ref"})
            else:
                rows.append({key: value for key, value in json.items() if key != "user_ref"})
            return httpx.Response(201, json=[])
        if method == "DELETE":
            self.lines["cart_lines"] = [
                entry
                for entry in self.lines["cart_lines"]
                if not url.endswith(f"product_ref=eq.{json}")
            ]
        return httpx.Response(204)


@pytest.mark.asyncio
async def test_supabase_add_upserts_line_with_image_and_accumulates_qty():
    transport = FakeTransport({})
    provider = SupabaseCartProvider("http://supabase", "key", StubCatalogProvider())
    async def mocked_request(method, path, json=None, headers=None):
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            request = client.build_request(
                method,
                f"http://supabase{path}",
                headers=headers,
                json=json,
            )
            response = await client.send(request)
            response.raise_for_status()
            return response.json()

    provider._request = mocked_request
    first = await provider.add("user", "baijiu-jiangxiang-500ml", 1)
    second = await provider.add("user", "baijiu-jiangxiang-500ml", 2)
    assert first[0].image_url is not None
    assert first[0].unit_price_cents == 32800
    assert second[0].qty == 3
    post = [request for request in transport.requests if request[0] == "POST"][-1]
    assert post[2]["title"] == "贵州酱香白酒 500ml"
    assert post[2]["qty"] == 3
    assert post[3]["prefer"] == "resolution=merge-duplicates"
