"""Read-only demo catalog for deterministic stateless retrieval."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class CatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_ref: str
    title: str
    keywords: list[str]
    price_cents: int
    currency: str = "CNY"
    category: str = "goods"
    subcategory: str
    image_url: str
    source: str
    marketplace_url: str
    unit_label: str | None = None
    unit_price_cents: int | None = None
    in_stock: bool = True
    compliance: list[str] = []


ITEMS: tuple[CatalogItem, ...] = (
    CatalogItem(product_ref="baijiu-jiangxiang-500ml", title="贵州酱香白酒 500ml", keywords=["贵州", "酱香", "白酒", "酒", "茅台镇", "酱酒", "baijiu"], price_cents=32800, category="goods", subcategory="baijiu", image_url="https://ddimg.cn/hotlink/sauce-baijiu.jpg", source="ddimg", marketplace_url="https://ddimg.cn/sauce-baijiu", unit_label="/500ml", unit_price_cents=32800, compliance=["ALCOHOL_CNY"]),
    CatalogItem(product_ref="maotai-town-500ml", title="茅台镇酱酒 500ml", keywords=["茅台镇", "酱酒", "酱香", "酒", "推荐"], price_cents=46800, category="goods", subcategory="baijiu", image_url="https://ddimg.cn/hotlink/maotai-town.jpg", source="ddimg", marketplace_url="https://ddimg.cn/maotai-town", unit_label="/500ml", unit_price_cents=46800, compliance=["ALCOHOL_CNY"]),
    CatalogItem(product_ref="maotai-town-100ml", title="茅台镇酱酒 100ml", keywords=["茅台镇", "酱酒", "小瓶"], price_cents=22800, category="goods", subcategory="baijiu", image_url="https://ddimg.cn/hotlink/maotai-100.jpg", source="ddimg", marketplace_url="https://ddimg.cn/maotai-100", unit_label="/100ml", unit_price_cents=228000, compliance=["ALCOHOL_CNY"]),
    CatalogItem(product_ref="collectors-baijiu-1l", title="陈年贵州酱香白酒 1L", keywords=["贵州", "酱香", "白酒", "陈年", "收藏"], price_cents=128000, category="goods", subcategory="baijiu", image_url="https://ddimg.cn/hotlink/aged.jpg", source="ddimg", marketplace_url="https://ddimg.cn/aged", unit_label="/1L", unit_price_cents=12800, compliance=["ALCOHOL_CNY"]),
    CatalogItem(product_ref="maotai-sold-out-500ml", title="茅台镇限量酱酒 500ml", keywords=["茅台镇", "限量", "售罄", "酱酒"], price_cents=58800, category="goods", subcategory="baijiu", image_url="https://ddimg.cn/hotlink/sold-out.jpg", source="ddimg", marketplace_url="https://ddimg.cn/sold-out", unit_label="/500ml", unit_price_cents=58800, in_stock=False, compliance=["ALCOHOL_CNY"]),
    CatalogItem(product_ref="tea-maojian-250g", title="都匀毛尖绿茶 250g", keywords=["茶", "绿茶", "毛尖", "特产"], price_cents=15800, category="goods", subcategory="tea", image_url="https://ddimg.cn/tea.jpg", source="ddimg", marketplace_url="https://ddimg.cn/tea", unit_label="/250g", unit_price_cents=6320),
    CatalogItem(product_ref="chili-guizhou-500g", title="贵州糊辣椒 500g", keywords=["辣椒", "糊辣椒", "调味"], price_cents=4800, category="goods", subcategory="seasoning", image_url="https://ddimg.cn/chili.jpg", source="ddimg", marketplace_url="https://ddimg.cn/chili", unit_label="/500g", unit_price_cents=960),
    CatalogItem(product_ref="silver-handmade", title="苗银手工手镯", keywords=["银饰", "苗族", "手镯", "礼物"], price_cents=88000, category="goods", subcategory="craft", image_url="https://ddimg.cn/silver.jpg", source="ddimg", marketplace_url="https://ddimg.cn/silver"),
    CatalogItem(product_ref="huangguoshu-ticket", title="黄果树瀑布景区门票", keywords=["黄果树", "门票", "瀑布", "景区"], price_cents=16000, category="ticket", subcategory="scenic_ticket", image_url="https://piaojia.cn/huanguo.jpg", source="piaojia", marketplace_url="https://piaojia.cn/huanguoshu", unit_label="/adult"),
    CatalogItem(product_ref="libo-ticket", title="荔波小七孔景区门票", keywords=["荔波", "门票", "小七孔", "景区"], price_cents=13000, category="ticket", subcategory="scenic_ticket", image_url="https://piaojia.cn/libo.jpg", source="piaojia", marketplace_url="https://piaojia.cn/libo", unit_label="/adult"),
    CatalogItem(product_ref="qingyan-ticket", title="青岩古镇联票", keywords=["青岩", "古镇", "门票", "联票"], price_cents=8000, category="ticket", subcategory="scenic_ticket", image_url="https://piaojia.cn/qingyan.jpg", source="piaojia", marketplace_url="https://piaojia.cn/qingyan", unit_label="/adult"),
    CatalogItem(product_ref="local-guide-4h", title="贵阳本地向导服务 4小时", keywords=["贵阳", "向导", "本地", "服务", "旅游"], price_cents=38000, category="local_service", subcategory="guide", image_url="https://piaojia.cn/guide.jpg", source="piaojia", marketplace_url="https://piaojia.cn/guide", unit_label="/4h"),
)


class CatalogProvider(Protocol):
    async def search(self, query: str, *, category: str | None = None) -> list[CatalogItem]: ...

    async def get(self, product_ref: str) -> CatalogItem | None: ...


class StubCatalogProvider:
    async def search(self, query: str, *, category: str | None = None) -> list[CatalogItem]:
        text = query.lower()
        candidates = [item for item in ITEMS if not category or item.category == category]
        scored: list[tuple[int, CatalogItem]] = []
        for item in candidates:
            if item.title.lower() == text:
                return [item]
            score = sum(
                1
                for keyword in item.keywords
                if keyword.lower() in text or text in keyword.lower()
            )
            if score:
                scored.append((score, item))
        return [item for _, item in sorted(scored, key=lambda pair: (-pair[0], pair[1].product_ref))]

    async def get(self, product_ref: str) -> CatalogItem | None:
        return next((item for item in ITEMS if item.product_ref == product_ref), None)
