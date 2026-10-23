"""Flavor descriptions from HTReviews.

The list API the crawl uses has no description; each flavor page has a short
one (in Russian) under the title.  After every rebuild, pages of matched
flavors that have no cached description are fetched and kept in
``descriptions.json``, so each page is read once.  Pages with no description
are remembered too and looked at again after a while.
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import time

import httpx

from app import config, store
from app.sources.htr import BASE
from app.text import has_cyrillic

log = logging.getLogger(__name__)

CACHE_FILE = "descriptions.json"
RETRY_EMPTY = 14 * 86400  # look again for a description that wasn't there
RETRY_FAILED = 3600  # page fetch failed: try again soon
CONCURRENCY = 3

_cache: dict[str, dict] | None = None


def cache() -> dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = store.load(CACHE_FILE, {}) or {}
    return _cache


def text(htr_id: int) -> str:
    """The description as HTR has it (Russian, or English for the few written
    in English); '' if there is none."""
    e = cache().get(str(htr_id)) or {}
    return e.get("ru") or e.get("en") or ""


def parse(page: str) -> str:
    m = re.search(r'<div class="object_card_discr">\s*(.*?)\s*</div>', page, re.S)
    if not m:
        return ""
    # Newlines in the markup are just source formatting; only <br> breaks a line.
    t = re.sub(r"\s+", " ", m.group(1))
    t = re.sub(r"\s*<br\s*/?>\s*", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


def _needs_fetch(entry: dict | None, now: float) -> bool:
    if not entry:
        return True
    age = now - entry.get("at", 0)
    if entry.get("err"):
        return age > RETRY_FAILED
    if entry.get("ru") or entry.get("en"):
        return False
    return age > RETRY_EMPTY


async def _fetch(client: httpx.AsyncClient, slug: str) -> dict:
    entry: dict = {"at": time.time()}
    try:
        r = await client.get(f"{BASE}/tobaccos/{slug}")
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("HTR description %s failed: %s", slug, e)
        return {**entry, "err": True}
    t = parse(r.text)
    if not t:
        return entry
    return {**entry, "en": t} if not has_cyrillic(t) else {**entry, "ru": t}


async def fill(flavors: list[tuple[int, str]], progress=None) -> int:
    """Fetch descriptions for ``[(htr id, slug), …]`` that aren't cached
    yet.  Returns how many were added."""
    c = cache()
    now = time.time()
    todo = [(i, s) for i, s in flavors if _needs_fetch(c.get(str(i)), now)]
    changed = 0
    async with httpx.AsyncClient(headers={"User-Agent": config.USER_AGENT}, timeout=30) as client:
        if todo:
            if progress:
                progress(f"Fetching {len(todo)} flavor descriptions from HTReviews…")
            sem = asyncio.Semaphore(CONCURRENCY)
            done = 0

            async def one(htr_id: int, slug: str) -> None:
                nonlocal done, changed
                async with sem:
                    e = await _fetch(client, slug)
                c[str(htr_id)] = e
                changed += bool(e.get("ru") or e.get("en"))
                done += 1
                if done % 100 == 0:
                    store.save(CACHE_FILE, c)
                    if progress:
                        progress(f"Descriptions: {done}/{len(todo)} pages")

            await asyncio.gather(*(one(i, s) for i, s in todo))
            store.save(CACHE_FILE, c)
    return changed
