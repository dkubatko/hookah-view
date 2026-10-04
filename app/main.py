"""HTTP layer: one precompressed catalog document plus a few admin endpoints.

The browser downloads the whole catalog once (~150 KB gzipped) and does all
filtering and sorting locally, so browsing never waits on the server.  The
document is rebuilt only when data changes; requests just serve bytes, with
an ETag so repeat visits revalidate with a 304.
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app import config, refresh, store
from app.build import english_name
from app.text import display_case, has_cyrillic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hookah")


class Doc:
    """A JSON document kept as raw + gzipped bytes with an ETag."""

    def __init__(self, data) -> None:
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        self.raw = raw
        self.gz = gzip.compress(raw, 6)
        self.etag = '"' + hashlib.sha1(raw).hexdigest()[:16] + '"'

    def response(self, request: Request) -> Response:
        if request.headers.get("if-none-match") == self.etag:
            return Response(status_code=304, headers={"ETag": self.etag})
        headers = {"ETag": self.etag, "Cache-Control": "no-cache", "Vary": "Accept-Encoding"}
        if "gzip" in request.headers.get("accept-encoding", ""):
            headers["Content-Encoding"] = "gzip"
            return Response(self.gz, media_type="application/json", headers=headers)
        return Response(self.raw, media_type="application/json", headers=headers)


class Cache:
    catalog: Doc | None = None
    stats: dict = {}
    htr_brands: dict[str, Doc] = {}

    @classmethod
    def set_catalog(cls, catalog: dict) -> None:
        cls.catalog = Doc(catalog)
        cls.stats = catalog.get("stats", {})
        cls.htr_brands = {}


refresh.state.on_catalog = Cache.set_catalog


def _static_version() -> str:
    h = hashlib.sha1()
    for p in sorted(config.STATIC_DIR.rglob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(str(p.stat().st_mtime_ns).encode())
    return h.hexdigest()[:10]


INDEX_HTML: bytes = b""


def _load_index() -> None:
    global INDEX_HTML
    html = (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    INDEX_HTML = html.replace("__V__", _static_version()).encode()


async def index(request: Request) -> Response:
    if config.COMMIT == "dev":
        _load_index()  # pick up edits without a restart while developing
    return Response(INDEX_HTML, media_type="text/html", headers={"Cache-Control": "no-cache"})


async def catalog(request: Request) -> Response:
    if Cache.catalog is None:
        return JSONResponse({"products": [], "loading": True}, status_code=503)
    return Cache.catalog.response(request)


async def status(request: Request) -> Response:
    return JSONResponse({**refresh.state.snapshot(), "stats": Cache.stats, "commit": config.COMMIT,
                         "admin_locked": bool(config.ADMIN_TOKEN)})


async def health(request: Request) -> Response:
    return JSONResponse({"ok": Cache.catalog is not None, "commit": config.COMMIT})


def _authorised(request: Request) -> bool:
    return not config.ADMIN_TOKEN or request.headers.get("x-admin-token") == config.ADMIN_TOKEN


async def start_refresh(request: Request) -> Response:
    if not _authorised(request):
        return JSONResponse({"error": "admin token required"}, status_code=401)
    body = await request.json() if await request.body() else {}
    kind = body.get("kind", "all")
    if kind not in ("whm", "htr", "all"):
        return JSONResponse({"error": "kind must be whm, htr or all"}, status_code=400)
    if refresh.state.lock.locked():
        return JSONResponse({"started": False, "running": refresh.state.running})
    asyncio.create_task(refresh.run(kind))
    return JSONResponse({"started": True})


async def htr_brand(request: Request) -> Response:
    """Every reviewed flavor of one brand, for the match-fix picker."""
    brand = request.path_params["brand"]
    if brand not in Cache.htr_brands:
        data = (store.load("htr.json", {}) or {}).get(brand)
        items = []
        for it in (data or {}).get("items", []):
            ru = it["name"] if has_cyrillic(it["name"]) else it["alt_name"]
            items.append({
                "id": it["id"],
                "n": english_name(it),
                "ru": ru if has_cyrillic(ru or "") else "",
                "line": display_case(it["line"]) if it["line"] != "Основная" else "",
                "r": it["rating"],
                "rc": it["ratings"],
                "u": it["slug"],
            })
        items.sort(key=lambda x: x["n"].lower())
        Cache.htr_brands[brand] = Doc({"brand": brand, "items": items})
    return Cache.htr_brands[brand].response(request)


async def set_match(request: Request) -> Response:
    """Pin a flavor to an HTR review (htr_id), mark it "no review" (null), or
    clear the pin (DELETE) so automatic matching applies again."""
    if not _authorised(request):
        return JSONResponse({"error": "admin token required"}, status_code=401)
    body = await request.json()
    key = body.get("key")
    if not key or not isinstance(key, str):
        return JSONResponse({"error": "key required"}, status_code=400)
    overrides = store.load("overrides.json", {}) or {}
    if request.method == "DELETE":
        overrides.pop(key, None)
    else:
        hid = body.get("htr_id")
        overrides[key] = {"htr_id": int(hid) if hid else None, "at": time.time()}
    store.save("overrides.json", overrides)
    async with refresh.state.lock:
        await asyncio.to_thread(refresh.rebuild)
    return JSONResponse({"ok": True, "etag": Cache.catalog.etag if Cache.catalog else None})


@asynccontextmanager
async def lifespan(app):
    _load_index()
    existing = store.load("catalog.json")
    if existing:
        Cache.set_catalog(existing)

    async def startup_rebuild():
        # Rebuild once so matching/code changes apply right after a deploy.
        async with refresh.state.lock:
            await asyncio.to_thread(refresh.rebuild)

    if existing:
        asyncio.create_task(startup_rebuild())
    task = asyncio.create_task(refresh.scheduler())
    yield
    task.cancel()


class Static(StaticFiles):
    """Assets are referenced with ?v=<hash>, so they can be cached forever."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code == 200 and b"v=" in scope.get("query_string", b""):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/catalog", catalog),
        Route("/api/status", status),
        Route("/api/health", health),
        Route("/api/refresh", start_refresh, methods=["POST"]),
        Route("/api/htr/{brand:path}", htr_brand),
        Route("/api/match", set_match, methods=["PUT", "DELETE"]),
        Mount("/static", Static(directory=Path(config.STATIC_DIR))),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=config.PORT, proxy_headers=True, forwarded_allow_ips="*")
