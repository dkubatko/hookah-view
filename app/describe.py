"""Flavor descriptions from HTReviews, fetched when someone opens a flavor.

The list API the crawl uses has no description; each flavor page has a short
one (in Russian) under the title.  Fetching ~1,800 pages on every crawl would
be slow and rude, so a description is fetched the first time a flavor is
opened, translated with ModernMT and kept in ``descriptions.json``.  Pages
with no description are remembered too, and checked again after a while.
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
RETRY_FAILED = 3600  # page or translation failed: try again soon

_cache: dict[str, dict] | None = None
_inflight: dict[int, asyncio.Task] = {}


def cache() -> dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = store.load(CACHE_FILE, {}) or {}
    return _cache


def parse(page: str) -> str:
    m = re.search(r'<div class="object_card_discr">\s*(.*?)\s*</div>', page, re.S)
    if not m:
        return ""
    # Newlines in the markup are just source formatting; only <br> breaks a line.
    text = re.sub(r"\s+", " ", m.group(1))
    text = re.sub(r"\s*<br\s*/?>\s*", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


async def _translate(client: httpx.AsyncClient, text: str) -> str | None:
    if not config.MODERNMT_API_KEY:
        return None
    try:
        r = await client.get(
            "https://api.modernmt.com/translate",
            params={"source": "ru", "target": "en", "q": text},
            headers={"MMT-ApiKey": config.MODERNMT_API_KEY},
        )
        r.raise_for_status()
        return (r.json()["data"].get("translation") or "").strip() or None
    except (httpx.HTTPError, KeyError, ValueError) as e:
        log.warning("ModernMT description failed: %s", e)
        return None


async def _fetch(htr_id: int, slug: str) -> dict:
    entry = {"at": time.time(), "ru": "", "en": "", "ok": True}
    async with httpx.AsyncClient(headers={"User-Agent": config.USER_AGENT}, timeout=20) as client:
        try:
            r = await client.get(f"{BASE}/tobaccos/{slug}")
            r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("HTR description %s failed: %s", slug, e)
            return {**entry, "ok": False}
        text = parse(r.text)
        if not text:
            return entry
        if not has_cyrillic(text):
            return {**entry, "en": text}
        en = await _translate(client, text)
        return {**entry, "ru": text, "en": en or "", "ok": en is not None}


def _fresh(entry: dict | None) -> bool:
    if not entry:
        return False
    age = time.time() - entry.get("at", 0)
    if not entry.get("ok", True):
        return age < RETRY_FAILED
    return bool(entry.get("en") or entry.get("ru")) or age < RETRY_EMPTY


async def get(htr_id: int, slug: str) -> dict:
    """``{"en": str, "ru": str}``; both empty if HTR has no description."""
    c = cache()
    key = str(htr_id)
    entry = c.get(key)
    if not _fresh(entry):
        task = _inflight.get(htr_id)
        if task is None:
            task = _inflight[htr_id] = asyncio.create_task(_fetch(htr_id, slug))
            task.add_done_callback(lambda _: _inflight.pop(htr_id, None))
        # Only empty or failed entries are refetched, so nothing is lost.
        entry = c[key] = await task
        await asyncio.to_thread(store.save, CACHE_FILE, c)
    return {"en": entry.get("en") or "", "ru": entry.get("ru") or ""}
