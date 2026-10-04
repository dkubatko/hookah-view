"""Data refresh jobs and the background schedule.

WHM (stock, prices) refreshes every couple of hours; HTR (ratings) daily.
Each job writes its raw data, then the catalog is rebuilt from disk, so a
failed fetch leaves the previous data in place.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from app import build, config, rules, store, translate
from app.parse import Taxonomy
from app.sources import htr as htr_source
from app.sources import whm as whm_source
from app.text import has_cyrillic, is_mostly_latin, slugify

log = logging.getLogger(__name__)


class State:
    def __init__(self) -> None:
        self.running: str | None = None
        self.message = ""
        self.log: deque[str] = deque(maxlen=40)
        self.meta = store.load("meta.json", {}) or {}
        self.lock = asyncio.Lock()
        self.on_catalog = None  # callback(catalog dict)

    def say(self, msg: str) -> None:
        self.message = msg
        self.log.append(f"{time.strftime('%H:%M:%S')} {msg}")
        log.info(msg)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "message": self.message,
            "log": list(self.log),
            "whm_at": self.meta.get("whm_at"),
            "htr_at": self.meta.get("htr_at"),
            "built_at": self.meta.get("built_at"),
            "error": self.meta.get("error"),
        }

    def mark(self, **kw) -> None:
        self.meta.update(kw)
        store.save("meta.json", self.meta)


state = State()


def htr_brand_slugs(whm: dict) -> dict[str, str]:
    tax = Taxonomy.build(whm["categories"])
    out = {}
    for brand in sorted(set(tax.brand_of.values())):
        r = rules.brand_rules(brand)
        if "htr" in r and r["htr"] is None:
            continue
        out[brand] = r.get("htr") or slugify(brand)
    return out


async def refresh_whm() -> None:
    state.say("Fetching World Hookah Market catalog…")
    data = await whm_source.fetch_all(progress=state.say)
    store.save("whm.json", data)
    state.mark(whm_at=time.time())
    state.say(f"WHM: {len(data['products'])} tobacco products")


async def refresh_htr() -> None:
    whm = store.load("whm.json")
    if not whm:
        await refresh_whm()
        whm = store.load("whm.json")
    brands = htr_brand_slugs(whm)
    state.say(f"Fetching HTReviews for {len(brands)} brands…")
    previous = store.load("htr.json", {}) or {}
    data = await htr_source.fetch_brands(brands, previous, progress=state.say)
    store.save("htr.json", data)
    # Same rule as match.candidate_strings: Russian names, plus Russian alt
    # names of flavors that have no Latin name at all.
    names = []
    for d in data.values():
        for it in (d or {}).get("items", []):
            latin = any(is_mostly_latin(x) for x in (it["name"], it["alt_name"]) if x)
            for s in (it["name"], it["alt_name"]):
                if s and has_cyrillic(s) and not is_mostly_latin(s) and (s == it["name"] or not latin):
                    names.append(s)
    added = await translate.ensure(names)
    if added:
        state.say(f"Translated {added} new Russian flavor names")
    state.mark(htr_at=time.time())
    total = sum(len(d["items"]) for d in data.values() if d)
    state.say(f"HTR: {total} reviewed flavors")


# Match results only change when HTR data does; reusing them makes a rebuild
# after a manual match fix or a stock refresh take a fraction of a second.
_memo: dict = {}


def rebuild() -> dict | None:
    whm = store.load("whm.json")
    htr = store.load("htr.json", {}) or {}
    if not whm:
        return None
    history = store.load("history.json", {}) or {}
    if _memo.get("sig") != state.meta.get("htr_at"):
        _memo.clear()
        _memo["sig"] = state.meta.get("htr_at")
    catalog = build.build(whm, htr, store.load("overrides.json", {}) or {}, history, memo=_memo)
    store.save("history.json", history)
    store.save("catalog.json", catalog)
    state.mark(built_at=catalog["built"])
    if state.on_catalog:
        state.on_catalog(catalog)
    return catalog


async def run(kind: str) -> bool:
    """kind: 'whm', 'htr' or 'all'.  Returns False if a job is already running."""
    if state.lock.locked():
        return False
    async with state.lock:
        state.running = kind
        try:
            if kind in ("whm", "all"):
                await refresh_whm()
            if kind in ("htr", "all"):
                await refresh_htr()
            state.say("Matching…")
            catalog = await asyncio.to_thread(rebuild)
            if catalog:
                s = catalog["stats"]
                state.say(
                    f"Done: {s['products']} flavors, {s['matched']} with ratings, "
                    f"{s['in_stock']} in stock"
                )
            state.mark(error=None)
        except Exception as e:
            log.exception("refresh failed")
            state.say(f"Refresh failed: {e}")
            state.mark(error=f"{type(e).__name__}: {e}")
        finally:
            state.running = None
    return True


RETRY_AFTER = 15 * 60  # after a failed fetch, don't hammer the source


async def scheduler() -> None:
    """Keep data fresh: WHM every WHM_REFRESH_MINUTES, HTR every HTR_REFRESH_HOURS."""
    tried = {"whm": 0.0, "htr": 0.0}
    await asyncio.sleep(5)
    while True:
        now = time.time()
        due = [
            kind
            for kind, every in (("whm", config.WHM_REFRESH_MINUTES * 60), ("htr", config.HTR_REFRESH_HOURS * 3600))
            if now - (state.meta.get(f"{kind}_at") or 0) > every and now - tried[kind] > RETRY_AFTER
        ]
        if due and not state.lock.locked():
            for kind in due:
                tried[kind] = now
            await run("all" if len(due) == 2 else due[0])
        await asyncio.sleep(60)
