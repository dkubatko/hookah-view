"""Build the served catalog from raw WHM + HTR data.

Pipeline: classify WHM products into brand/line/flavor -> group sizes of the
same flavor -> match each flavor (not each size) to HTR, overrides first ->
resolve two flavors claiming one review -> merge listings of one product
split across WHM categories -> derive prices, confidence-weighted ratings
and stock history.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict

from rapidfuzz import fuzz

from app import rules
from app.match import THRESHOLD, BrandIndex, best_match, build_index
from app.parse import Taxonomy, extract_flavor, grams
from app.text import display_case, fix_homoglyphs, has_cyrillic, is_mostly_latin, norm, slugify
from app import translate, vocab

log = logging.getLogger(__name__)

HTR_BASE = "https://htreviews.org"
PRIOR_WEIGHT = 15  # ratings needed before an item's own average dominates
NEW_DAYS = 14


def product_key(brand: str, line: str, key: str) -> str:
    return f"{slugify(brand)}/{slugify(line) or 'main'}/{slugify(key) or 'x'}"


def htr_line_slugs(brand: str, line: str, htr_lines: dict[str, str]) -> set[str] | None:
    """HTR line slugs that correspond to a WHM line, or None if unknown."""
    explicit = (rules.brand_rules(brand).get("lines") or {}).get(line)
    if explicit:
        return set(explicit)
    if not htr_lines:
        return None
    if not line:
        mains = {s for s, n in htr_lines.items() if s.endswith("main") or n == "Основная"}
        if mains:
            return mains
        return set(htr_lines) if len(htr_lines) == 1 else None
    want = set(norm(line).split())
    found = set()
    for slug, name in htr_lines.items():
        words = set(norm(slug.replace("-", " ")).split()) | set(norm(name).split())
        if want <= words or fuzz.token_set_ratio(norm(line), norm(name)) >= 90:
            found.add(slug)
    return found or None


def english_name(item: dict) -> str:
    name, alt = fix_homoglyphs(item["name"]), fix_homoglyphs(item["alt_name"])
    for s in (name, alt):
        if s and is_mostly_latin(s):
            return s
    for s in (name, alt):
        if s and has_cyrillic(s) and (t := translate.lookup(s)):
            return t[0][:1].upper() + t[0][1:]
    return name


def _htr_payload(item: dict, brand_slug: str) -> dict:
    strength = vocab.STRENGTH.get(item.get("strength") or "")
    tags = []
    for name, _group in item.get("tags") or []:
        tags.append(vocab.TAGS.get(name, name))
    ru = item["name"] if has_cyrillic(item["name"]) else item["alt_name"]
    return {
        "id": item["id"],
        "n": english_name(item),
        "ru": ru if has_cyrillic(ru or "") else "",
        "u": item["slug"],
        "line": display_case(item.get("line") or "") if item.get("line") != "Основная" else "",
        "r": item.get("rating"),
        "rc": item.get("ratings") or 0,
        "rv": item.get("reviews") or 0,
        "st": strength[1] if strength else 0,
        "stat": vocab.STATUS.get(item.get("status") or "", item.get("status") or ""),
        "tags": tags,
        "img": f"{HTR_BASE}/{item['image']}" if item.get("image") else "",
    }


def build(
    whm: dict, htr: dict, overrides: dict, history: dict, now: float | None = None, memo: dict | None = None
) -> dict:
    now = now or time.time()
    t0 = time.time()
    tax = Taxonomy.build(whm["categories"])

    # ── 1. classify + group sizes ────────────────────────────────────────
    groups: dict[tuple[str, str, str], dict] = {}
    skipped = 0
    for p in whm["products"]:
        c = tax.classify(p["categories"])
        if not c or not p.get("price"):
            skipped += 1
            continue
        brand, line, russian, cat_name = c
        fl = extract_flavor(p["name"], brand, line, tax.lines_by_brand.get(brand, set()))
        line = fl.line or line
        k = (brand, line, fl.key)
        g = groups.get(k)
        if g is None:
            g = groups[k] = {
                "brand": brand, "line": line, "name": fl.name, "notes": fl.notes,
                "variants": fl.variants, "russian": russian, "sizes": [],
                "keys": [product_key(brand, line, fl.key)],
            }
        g["russian"] |= russian
        g["notes"] = g["notes"] or fl.notes
        g["sizes"].append({
            "id": p["id"],
            "g": grams(p["name"]) or grams(cat_name),
            "p": p["price"],
            "rp": p["regular_price"] if p.get("on_sale") else None,
            "st": p["in_stock"],
            "u": p["url"],
            "img": p.get("image") or "",
        })

    # ── 2. match each flavor against its brand on HTR ────────────────────
    by_id: dict[int, tuple[dict, str]] = {}
    brand_meta: dict[str, dict] = {}
    for brand, data in htr.items():
        if not data:
            continue
        for it in data["items"]:
            by_id[it["id"]] = (it, data["slug"])
        brand_meta[brand] = data

    _indexes: dict[str, BrandIndex] = {}

    def index_for(brand: str) -> BrandIndex | None:
        # Built lazily: with memoised matches most rebuilds need none.
        data = brand_meta.get(brand)
        if not data:
            return None
        if brand not in _indexes:
            names = [brand, data["meta"].get("name", ""), data["meta"].get("alt_name", "")]
            _indexes[brand] = build_index(
                data["items"], [n for n in names if n], rules.brand_rules(brand).get("htr_suffixes", [])
            )
        return _indexes[brand]
    htr_lines = {
        b: {it["line_slug"]: it["line"] for it in d["items"]} for b, d in brand_meta.items()
    }

    for g in groups.values():
        g["line_slugs"] = htr_line_slugs(g["brand"], g["line"], htr_lines.get(g["brand"], {}))
        ov = next((overrides[k] for k in g["keys"] if k in overrides), None)
        if ov is not None:
            hid = ov.get("htr_id")
            g["match"] = (by_id.get(hid, (None,))[0] if hid else None, 100.0, True)
            continue
        if g["brand"] not in brand_meta:
            g["match"] = (None, 0.0, False)
            continue
        mk = (g["brand"], tuple(g["variants"]), tuple(sorted(g["line_slugs"] or ())))
        if memo is not None and mk in memo:
            hid, sc = memo[mk]
        else:
            res = best_match(g["variants"], index_for(g["brand"]), g["line_slugs"])
            hid, sc = (res.item["id"] if res.item else None), res.score
            if memo is not None:
                memo[mk] = (hid, sc)
        g["match"] = (by_id[hid][0] if hid else None, sc, False)

    # ── 3. merge one product listed under several WHM categories ─────────
    # WHM files sizes of one flavor under different categories and spells
    # them differently ("Grape with Mint 50g" / "Grapes with Mint 250g";
    # Darkside "Pear 100g" / "Base Pear 200g").  Listings of a brand that
    # confidently matched the same review, or share a name, are one product
    # unless they sit in two different named lines.
    merged: list[dict] = []
    by_review: dict[tuple[str, int], list[dict]] = defaultdict(list)
    by_name: dict[tuple[str, str], list[dict]] = defaultdict(list)

    def compatible(a: dict, b: dict) -> bool:
        return not a["line"] or not b["line"] or a["line"] == b["line"]

    for g in sorted(groups.values(), key=lambda x: (x["line"] == "", -len(x["sizes"]))):
        item, sc, manual = g["match"]
        name_key = (g["brand"], norm(g["variants"][0]))
        pool = list(by_name[name_key])
        if item and (sc >= 85 or manual):
            pool += by_review[(g["brand"], item["id"])]
        target = next(
            (m for m in pool if compatible(m, g) and (not item or not m["match"][0] or m["match"][0]["id"] == item["id"])),
            None,
        )
        if target is not None:
            target["sizes"] += g["sizes"]
            target["keys"] += g["keys"]
            target["russian"] |= g["russian"]
            target["line"] = target["line"] or g["line"]
            if not target["match"][0] and item:
                target["match"] = g["match"]
            continue
        merged.append(g)
        by_name[name_key].append(g)
        if item and (sc >= 85 or manual):
            by_review[(g["brand"], item["id"])].append(g)

    # ── 5. history: first seen / back in stock ───────────────────────────
    skus = history.setdefault("skus", {})
    history.setdefault("baseline", now)
    for g in merged:
        for s in g["sizes"]:
            h = skus.setdefault(str(s["id"]), {"f": now, "s": now if s["st"] else None})
            if s["st"] and not h.get("s"):
                h["s"] = now
            elif not s["st"]:
                h["s"] = None

    # ── 6. serialise ────────────────────────────────────────────────────
    rated = [it for it, _ in by_id.values() if it.get("rating") and it.get("ratings", 0) >= 5]
    prior = (sum(i["rating"] for i in rated) / len(rated)) if rated else 4.0
    baseline = history["baseline"]
    products = []
    matched = manual = 0
    for g in merged:
        # Duplicate listings of the same size: keep one, preferring in stock.
        sizes = sorted(g["sizes"], key=lambda s: (s["g"] or 0, s["p"], not s["st"]))
        dedup: dict = {}
        for s in sizes:
            dedup.setdefault((s["g"], s["p"]), s)
        sizes = list(dedup.values())
        in_stock = [s for s in sizes if s["st"]]
        per_g = [s["p"] / s["g"] for s in (in_stock or sizes) if s["g"]]
        item, sc, is_manual = g["match"]
        h = None
        if item:
            matched += 1
            manual += is_manual
            h = _htr_payload(item, by_id[item["id"]][1])
        r, rc = (h["r"], h["rc"]) if h and h["r"] else (None, 0)
        bayes = (prior * PRIOR_WEIGHT + r * rc) / (PRIOR_WEIGHT + rc) if r else None
        first = min(skus[str(s["id"])]["f"] for s in sizes)
        restock = max((skus[str(s["id"])]["s"] or 0) for s in sizes)
        img = next((s["img"] for s in in_stock + sizes if s["img"]), "") or (h["img"] if h else "")
        products.append({
            "k": g["keys"][0],
            "keys": g["keys"][1:],
            "b": g["brand"],
            "l": g["line"],
            "n": g["name"],
            "nt": g["notes"],
            "ru": g["russian"],
            "img": img,
            "s": [{k: v for k, v in s.items() if k != "img"} for s in sizes],
            "stock": bool(in_stock),
            "pmin": min(s["p"] for s in (in_stock or sizes)),
            "ppg": round(min(per_g), 4) if per_g else None,
            "h": h,
            "score": round(bayes, 3) if bayes else None,
            "ms": round(sc) if item else (round(sc) if sc else 0),
            "mo": bool(is_manual),
            "new": first if first > baseline + 3600 else None,
            "back": restock if restock and restock - first > 86400 else None,
        })

    brands = {}
    for p in products:
        b = brands.setdefault(p["b"], {"n": 0, "lines": set(), "ru": False})
        b["n"] += 1
        b["ru"] |= p["ru"]
        if p["l"]:
            b["lines"].add(p["l"])
    for name, b in brands.items():
        meta = brand_meta.get(name)
        b["lines"] = sorted(b["lines"])
        b["htr"] = meta["slug"] if meta else None
        country = meta["meta"].get("country", "") if meta else ""
        b["country"] = vocab.COUNTRY.get(country, country)

    tags = {}
    for it, _ in by_id.values():
        for name, group in it.get("tags") or []:
            tags.setdefault(vocab.TAGS.get(name, name), group)
    groups_out = [
        {"key": label, "color": color, "ru": ru}
        for ru, (label, color) in vocab.GROUPS.items()
    ]
    tag_group = {t: vocab.GROUPS.get(g, (g, ""))[0] for t, g in tags.items()}

    stats = {
        "products": len(products),
        "skus": sum(len(p["s"]) for p in products),
        "in_stock": sum(p["stock"] for p in products),
        "matched": matched,
        "manual": manual,
        "unmatchable": sum(1 for p in products if not brand_meta.get(p["b"])),
        "skipped": skipped,
        "build_ms": round((time.time() - t0) * 1000),
    }
    log.info("built catalog: %s", stats)
    return {
        "built": now,
        "products": products,
        "brands": brands,
        "groups": groups_out,
        "tag_group": tag_group,
        "stats": stats,
        "threshold": THRESHOLD,
        "tracking_since": baseline,
    }
