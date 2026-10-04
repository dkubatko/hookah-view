"""World Hookah Market (WooCommerce Store API) client.

Everything we sell-side care about lives under the "Hookah Tobacco" product
category (id 91), so we page through that category only (~35 requests)
instead of the whole 5k-product catalog.  Pages are ordered by id so the
listing is stable while we page through it, and the result is checked
against the API's X-WP-Total: a partial catalog is never returned, because
products missing from it would look discontinued.
"""
from __future__ import annotations

import asyncio
import html
import logging

import httpx

from app import config

log = logging.getLogger(__name__)

API = "https://worldhookahmarket.com/wp-json/wc/store/v1"
TOBACCO_CATEGORY = 91
PER_PAGE = 100
CONCURRENCY = 6


class WhmError(RuntimeError):
    pass


async def _get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(4):
        try:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                return r
            last = WhmError(f"HTTP {r.status_code} for {url} {params}")
        except httpx.HTTPError as e:
            last = e
        await asyncio.sleep(1.5 * 2**attempt)
    raise WhmError(f"WHM request failed: {last}")


async def fetch_categories(client: httpx.AsyncClient) -> list[dict]:
    cats: list[dict] = []
    page = 1
    while True:
        r = await _get(client, f"{API}/products/categories", {"per_page": 100, "page": page})
        batch = r.json()
        cats.extend(batch)
        if len(batch) < 100:
            return cats
        page += 1


async def fetch_products(client: httpx.AsyncClient, progress=None) -> list[dict]:
    base = {
        "category": TOBACCO_CATEGORY,
        "per_page": PER_PAGE,
        "orderby": "id",
        "order": "asc",
    }
    first = await _get(client, f"{API}/products", {**base, "page": 1})
    total = int(first.headers.get("x-wp-total", "0"))
    pages = int(first.headers.get("x-wp-totalpages", "1"))
    products = {p["id"]: p for p in first.json()}
    sem = asyncio.Semaphore(CONCURRENCY)
    done = 1

    async def one(page: int) -> None:
        nonlocal done
        async with sem:
            r = await _get(client, f"{API}/products", {**base, "page": page})
        for p in r.json():
            products[p["id"]] = p
        done += 1
        if progress:
            progress(f"WHM: {done}/{pages} pages")

    await asyncio.gather(*(one(p) for p in range(2, pages + 1)))
    # Products added/removed mid-crawl can shift a page boundary; tolerate a
    # handful but refuse anything that looks like a truncated catalog.
    if total and len(products) < total - 5:
        raise WhmError(f"WHM returned {len(products)} of {total} products")
    return list(products.values())


def _slim(p: dict) -> dict:
    """Keep only the fields the catalog builder needs."""
    prices = p.get("prices") or {}
    minor = int(prices.get("currency_minor_unit") or 2)

    def money(key: str) -> float | None:
        raw = prices.get(key)
        try:
            return int(raw) / 10**minor if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None

    image = (p.get("images") or [{}])[0]
    return {
        "id": p["id"],
        "name": html.unescape(p.get("name", "")),
        "url": p.get("permalink", ""),
        "price": money("price"),
        "regular_price": money("regular_price"),
        "on_sale": bool(p.get("on_sale")),
        "in_stock": bool(p.get("is_in_stock")),
        "purchasable": bool(p.get("is_purchasable")),
        "image": image.get("thumbnail") or image.get("src") or "",
        "categories": [c["id"] for c in p.get("categories", [])],
    }


async def fetch_all(progress=None) -> dict:
    async with httpx.AsyncClient(
        headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
        timeout=30,
        http2=False,
    ) as client:
        cats, products = await asyncio.gather(
            fetch_categories(client), fetch_products(client, progress)
        )
    return {
        "categories": [
            {
                "id": c["id"],
                "parent": c["parent"],
                "slug": c["slug"],
                "name": html.unescape(c["name"]),
            }
            for c in cats
        ],
        "products": [_slim(p) for p in products],
    }
