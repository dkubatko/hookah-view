import pytest

from app import translate
from app.build import build, htr_line_slugs
from app.match import THRESHOLD, best_match, build_index, score


@pytest.fixture(autouse=True)
def offline_translations(monkeypatch):
    table = {
        "виноград": ["Grape", "Grapes"],
        "арбуз и дыня": ["Watermelon and melon"],
        "клубника": ["Strawberry"],
        "земляника": ["Wild strawberry", "Strawberry"],
        "каспийский вайб": ["Caspian vibe"],
    }
    monkeypatch.setattr(translate, "lookup", lambda s: table.get(s.lower(), []))


def item(i, name, alt="", line="main", status="Выпускается", ratings=10, rating=4.5):
    slug = name.lower().replace(" ", "-")
    return {"id": i, "slug": f"b/{line}/{slug}", "name": name, "alt_name": alt, "line": line, "line_slug": line,
            "rating": rating, "ratings": ratings, "reviews": ratings, "strength": "Средняя", "status": status,
            "image": "", "tags": [["Мята", "Освежающий"]]}


def test_half_match_is_rejected():
    # "Orange Mint" must not land on plain "Orange"
    idx = build_index([item(1, "Orange"), item(2, "Mint")], ["Brand"])
    assert best_match(["Orange Mint"], idx, None).item is None


def test_spacing_and_spelling_variants():
    assert score("bubblegum", "bubble gum") == 100
    assert score("earl gray", "earl grey") >= THRESHOLD
    assert score("white gummy bear", "white gummi bear") >= THRESHOLD


def test_exact_name_beats_crowded_prefilter():
    items = [item(i, f"Cherry {w}") for i, w in enumerate("abcdefghijklmnopqrstuvwxyz", 10)]
    items.append(item(1, "Cherry", line="voda"))
    idx = build_index(items, ["Element"])
    assert best_match(["Cherry"], idx, {"voda"}).item["id"] == 1


def test_russian_name_is_translated_even_with_marketing_alt():
    idx = build_index([item(1, "Арбуз и дыня", alt="Wonder melon"), item(2, "Watermelon")], ["Sebero"])
    assert best_match(["Watermelon Melon"], idx, None).item["id"] == 1


def test_main_translation_beats_alternate():
    idx = build_index([item(1, "Клубника"), item(2, "Земляника")], ["Nash"])
    assert best_match(["Strawberry"], idx, None).item["id"] == 1


def test_renamed_flavor_alias():
    idx = build_index([item(1, "Клубника Ананас", alt="ex. White Strawberry")], ["Nash"])
    assert best_match(["White Strawberry"], idx, None).item["id"] == 1


def test_line_affinity_prefers_same_line():
    idx = build_index([item(1, "Pear", line="core"), item(2, "Pear", line="base")], ["Darkside"])
    assert best_match(["Pear"], idx, {"base"}).item["id"] == 2


def test_brand_suffix_trimming():
    idx = build_index([item(1, "Каспийский вайб", line="shot")], ["Darkside"], suffixes=["vibe"])
    assert best_match(["Caspian"], idx, None).item["id"] == 1


def test_htr_line_slugs():
    lines = {"tangiers-noir": "Tangiers Noir", "tangiers-burley": "Tangiers Burley"}
    assert htr_line_slugs("Tangiers", "Noir", lines) == {"tangiers-noir"}
    assert htr_line_slugs("Element", "Air", {"vozdukh": "Воздух"}) == {"vozdukh"}
    assert htr_line_slugs("Adalya", "", {"adalya-main": "Основная", "adalya-black": "Adalya Black"}) == {"adalya-main"}


CATS = [
    {"id": 91, "parent": 0, "slug": "tobacco", "name": "Hookah Tobacco"},
    {"id": 128, "parent": 91, "slug": "al-fakher-tobacco", "name": "AL Fakher Tobacco"},
    {"id": 129, "parent": 128, "slug": "al-fakher-50gr", "name": "Al Fakher 50gr"},
    {"id": 131, "parent": 128, "slug": "al-fakher-250gr", "name": "Al Fakher 250gr"},
]


def prod(i, name, cat, price, stock=True):
    return {"id": i, "name": name, "url": f"https://whm/{i}", "price": price, "regular_price": price,
            "on_sale": False, "in_stock": stock, "purchasable": True, "image": "", "categories": [cat]}


def test_build_merges_sizes_and_applies_overrides():
    whm = {"categories": CATS, "products": [
        prod(1, "Al Fakher – Grape with Mint 50gr", 129, 4.0),
        prod(2, "Al Fakher – GRAPES WITH MINT – 250g", 131, 15.0, stock=False),
        prod(3, "Al Fakher – Mint – 250g", 131, 15.0),
    ]}
    htr = {"Al Fakher": {"slug": "al-fakher", "meta": {"name": "Al Fakher", "alt_name": "", "country": "ОАЭ"},
                         "items": [item(10, "Grape with mint", line="al-fakher-main"), item(11, "Mint", line="al-fakher-main")]}}
    cat = build(whm, htr, {}, {})
    by_name = {p["n"]: p for p in cat["products"]}
    assert len(cat["products"]) == 2
    grape = by_name["Grape with Mint"]
    assert [s["g"] for s in grape["s"]] == [50, 250]
    assert grape["h"]["id"] == 10 and grape["stock"]
    assert grape["ppg"] == pytest.approx(4.0 / 50)
    assert cat["brands"]["Al Fakher"]["country"] == "UAE"

    # A manual "not on HTReviews" pin wins over the automatic match.
    cat = build(whm, htr, {by_name["Mint"]["k"]: {"htr_id": None}}, {})
    mint = next(p for p in cat["products"] if p["n"] == "Mint")
    assert mint["h"] is None and mint["mo"]
