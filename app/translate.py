"""Russian -> English translation of HTR flavor names, with a disk cache.

About a quarter of HTR flavors (Nash, Sarma, Severnyi, Starline, much of
Element/Chabacco/Sebero) only have a Russian name.  ModernMT returns a main
translation plus alternatives for the same price, and every variant becomes
a match candidate, so a loanword mistranslated by the top pick still has a
chance.  Translations never change, so each name is paid for once.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app import config, store
from app.text import norm

log = logging.getLogger(__name__)

CACHE_FILE = "translations.json"
API = "https://api.modernmt.com/translate"
BATCH = 64  # ModernMT accepts up to 128 phrases per request

_cache: dict[str, list[str]] | None = None


def cache() -> dict[str, list[str]]:
    global _cache
    if _cache is None:
        _cache = store.load(CACHE_FILE, {}) or {}
    return _cache


def lookup(name: str) -> list[str]:
    return cache().get(norm(name), [])


async def ensure(names: list[str]) -> int:
    """Translate any names not in the cache.  Returns how many were added."""
    c = cache()
    todo = sorted({norm(n) for n in names if n} - c.keys())
    if not todo:
        return 0
    if not config.MODERNMT_API_KEY:
        log.warning("%d names need translation but MODERNMT_API_KEY is not set", len(todo))
        return 0
    added = 0
    async with httpx.AsyncClient(timeout=60, headers={"MMT-ApiKey": config.MODERNMT_API_KEY}) as client:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i : i + BATCH]
            params = [("source", "ru"), ("target", "en"), ("alt_translations", "6")]
            params += [("q", q) for q in chunk]
            try:
                r = await client.get(API, params=params)
                r.raise_for_status()
                data = r.json()["data"]
                if isinstance(data, dict):
                    data = [data]
            except (httpx.HTTPError, KeyError, ValueError) as e:
                log.warning("ModernMT batch failed: %s", e)
                continue
            for src, res in zip(chunk, data):
                variants: list[str] = []
                for v in [res.get("translation", ""), *(res.get("altTranslations") or [])]:
                    v = (v or "").strip()
                    if v and norm(v) not in {norm(x) for x in variants}:
                        variants.append(v)
                if variants:
                    c[src] = variants
                    added += 1
    if added:
        store.save(CACHE_FILE, c)
    return added


def seed_from_legacy(legacy: dict) -> int:
    """Import the old app's ``.translations.json`` ({name: [variants]})."""
    c = cache()
    added = 0
    for k, v in legacy.items():
        vs = [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)]
        key = norm(k)
        if key and vs and key not in c:
            c[key] = vs
            added += 1
    if added:
        store.save(CACHE_FILE, c)
    return added


if __name__ == "__main__":  # python -m app.translate <legacy .translations.json>
    import json
    import sys

    print(seed_from_legacy(json.load(open(sys.argv[1], encoding="utf-8"))), "seeded")
