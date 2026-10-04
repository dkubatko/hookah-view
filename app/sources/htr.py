"""HTReviews client.

HTR has no public API, but its own pages load their tobacco lists from
``POST /postData {"action": "objectByBrand", ...}``, which returns rich JSON
per flavor: English + Russian names, rating, rating count, strength,
production status, flavor tags and an image.  One brand page fetch gives the
brand's object id; the list is then paged 100 at a time until empty.

That is ~4 requests per brand.  The old scraper also fetched every product
page to find English names; the list API already carries them.
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from rapidfuzz import fuzz

from app import config
from app.text import norm

log = logging.getLogger(__name__)

BASE = "https://htreviews.org"
PAGE = 100
CONCURRENCY = 3


class HtrError(RuntimeError):
    pass


async def _request(client: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(4):
        try:
            r = await client.request(method, url, **kw)
            if r.status_code < 500:
                return r
            last = HtrError(f"HTTP {r.status_code} for {url}")
        except httpx.HTTPError as e:
            last = e
        await asyncio.sleep(1.5 * 2**attempt)
    raise HtrError(f"HTR request failed: {last}")


def _info(page: str, label: str) -> str:
    m = re.search(
        rf"<span>{label}</span>\s*<span></span>\s*<(?:div|span)>\s*(.*?)\s*</(?:div|span)>",
        page,
        re.S,
    )
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""


def parse_brand_page(page: str) -> dict | None:
    oid = re.search(r'class="object_wrapper" data-id="(\d+)"', page)
    if not oid:
        return None
    title = re.search(r'<div class="object_card_title">\s*<h1>(.*?)</h1>\s*<span>(.*?)</span>', page, re.S)
    count = re.search(r'tobacco_list_items"[^>]*data-count="(\d+)"', page)
    return {
        "object_id": int(oid.group(1)),
        "name": title.group(1).strip() if title else "",
        "alt_name": title.group(2).strip() if title else "",
        "country": _info(page, "Страна"),
        "count": int(count.group(1)) if count else 0,
    }


async def resolve_brand(client: httpx.AsyncClient, brand: str, slug: str) -> tuple[str, dict] | None:
    """Find the HTR brand page for a shop brand: try the slug, then HTR search."""
    r = await _request(client, "GET", f"{BASE}/tobaccos/{slug}", follow_redirects=False)
    if r.status_code == 200 and (meta := parse_brand_page(r.text)):
        return slug, meta
    r = await _request(
        client,
        "GET",
        f"{BASE}/getData",
        params={"action": "search", "text": brand, "l": 10, "o": 0},
    )
    try:
        found = r.json()
    except ValueError:
        return None
    brands = found.get("brands", []) if isinstance(found, dict) else []
    if isinstance(brands, dict):
        brands = list(brands.values())
    # Search is substring-based ("Platinum Seven" finds "Seven"), so demand a
    # close match on the whole name before trusting it.
    best = max(
        brands,
        key=lambda b: fuzz.ratio(norm(brand), norm(b.get("name", ""))),
        default=None,
    )
    if not best or fuzz.ratio(norm(brand), norm(best.get("name", ""))) < 85:
        return None
    r = await _request(client, "GET", f"{BASE}/tobaccos/{best['slug']}", follow_redirects=False)
    if r.status_code == 200 and (meta := parse_brand_page(r.text)):
        return best["slug"], meta
    return None


async def fetch_brand_items(client: httpx.AsyncClient, object_id: int) -> list[dict]:
    items: dict[str, dict] = {}
    offset = 0
    while True:
        payload = {
            "action": "objectByBrand",
            "data": {"id": object_id, "limit": PAGE, "offset": offset, "sort": {"s": None, "d": None}},
        }
        r = await _request(client, "POST", f"{BASE}/postData", json=payload)
        batch = r.json() if r.status_code == 200 else None
        if not batch or not isinstance(batch, list):
            break
        for it in batch:
            items[it["slug"]] = it
        offset += len(batch)
        if offset > 5000:  # safety valve
            break
    return list(items.values())


def _int(v) -> int:
    try:
        return int(str(v).replace(" ", ""))
    except (TypeError, ValueError):
        return 0


def slim_item(it: dict) -> dict:
    rating = it.get("rating")
    try:
        rating = float(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None
    ratings = _int(it.get("ratings_count"))
    if not ratings or rating == 0:
        rating = None
    return {
        "id": int(it["id"]),
        "slug": it["slug"],
        "name": (it.get("name") or "").strip(),
        "alt_name": (it.get("alt_name") or "").strip(),
        "line": it.get("line") or "",
        "line_slug": (it.get("line_slug") or "").split("/", 1)[-1],
        "rating": rating,
        "ratings": ratings,
        "reviews": _int(it.get("reviews")),
        "strength": it.get("strength") or "",
        "status": it.get("status") or "",
        "image": it.get("media") or "",
        "tags": [[t.get("name", ""), t.get("group", "")] for t in it.get("tags") or []],
    }


async def fetch_brands(brands: dict[str, str], previous: dict, progress=None) -> dict:
    """Crawl HTR for ``{shop brand: guessed slug}``.

    Returns ``{shop brand: {"slug", "meta", "items"} | None}``.  A brand that
    fails to load keeps its previous data so one flaky request can't wipe
    ratings off the shop.
    """
    sem = asyncio.Semaphore(CONCURRENCY)
    out: dict[str, dict | None] = {}
    done = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": config.USER_AGENT}, timeout=30
    ) as client:

        async def one(brand: str, slug: str) -> None:
            nonlocal done
            async with sem:
                try:
                    resolved = await resolve_brand(client, brand, slug)
                    if resolved is None:
                        out[brand] = None
                    else:
                        real_slug, meta = resolved
                        raw = await fetch_brand_items(client, meta["object_id"])
                        out[brand] = {
                            "slug": real_slug,
                            "meta": meta,
                            "items": [slim_item(i) for i in raw],
                        }
                        if meta["count"] and len(raw) < meta["count"] * 0.9:
                            log.warning("HTR %s: got %d of %d items", real_slug, len(raw), meta["count"])
                except Exception as e:  # keep going; fall back to old data
                    log.warning("HTR %s failed: %s", brand, e)
                    out[brand] = previous.get(brand)
            done += 1
            if progress:
                progress(f"HTR: {done}/{len(brands)} brands")

        await asyncio.gather(*(one(b, s) for b, s in brands.items()))
    return out
