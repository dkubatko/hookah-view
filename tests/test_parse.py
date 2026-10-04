import pytest

from app.parse import Taxonomy, extract_flavor, grams
from app.text import display_case, norm

LINES = {
    "Darkside": {"Base", "Core", "Shot", "Xperience"},
    "Element": {"Air", "Earth", "Water", "V"},
    "Kraken": {"Caviar", "Medium Seco", "Strong Ligero", "Pro Fumelier", "Cigar for Hookah"},
    "Severnyi": {"Booster", "Professional", "Sorbet"},
    "Starbuzz": {"Bold"},
    "Trifecta": {"Blonde", "Dark Blend"},
    "Satyr": {"Aroma", "Old School", "Brilliant"},
    "Sarma": {"Classic", "Hard", "Soft"},
    "Trofimoff's": {"Burley", "Terror", "No Aroma"},
}


@pytest.mark.parametrize(
    "raw, brand, line, name",
    [
        ("Al Fakher – ORANGE WITH MINT – 250g", "Al Fakher", "", "Orange with Mint"),
        ("DarkSide RAF IN THE JUNGLE 250gr (Original Russian package)", "Darkside", "", "Raf in the Jungle"),
        ("DarkSide Xperience Petrol Headz Core 200G", "Darkside", "Xperience", "Petrol Headz"),
        ("DarkSide Wild Shake Base 200G", "Darkside", "Base", "Wild Shake"),
        ("DarkSide Shot #3 Ohotski 125gr", "Darkside", "Shot", "Ohotski"),
        ("DarkSide Kalee Grapefruit 2.0 200G", "Darkside", "Core", "Kalee Grapefruit 2.0"),
        ("Element Tobacco Berry Chups (Air Line)- 200gr", "Element", "Air", "Berry Chups"),
        ("Kraken Lychee-Strawberry 100GR (Medium Seco)", "Kraken", "Medium Seco", "Lychee-Strawberry"),
        ("SEVERNYI TOBACCO SORBET – “Grape Sorbet” 100G", "Severnyi", "Sorbet", "Grape"),
        ("Starbuzz Bold Exotic Irish Peach® 250gr", "Starbuzz", "Bold", "Irish Peach"),
        ("Trifecta Tobacco 250G Blonde | Cherry Berry", "Trifecta", "Blonde", "Cherry Berry"),
        ("Satyr Old School – Qirim Chacha 100G", "Satyr", "Old School", "Qirim Chacha"),
        ("Tangiers Lemongrass TC 05 250gr", "Tangiers", "Noir", "Lemongrass"),
        ("Tangiers Mexican Mocha 250gr (#67)", "Tangiers", "Noir", "Mexican Mocha"),
        ("Sarma Watermelon – Christmas Tree Hard 100G", "Sarma", "Hard", "Watermelon Christmas Tree"),
        ("Trofimoff’s Mango 125gr Terror", "Trofimoff's", "Terror", "Mango"),
        ("MUSTHAVE YOLKA (Christmas Tree) 125gr", "MustHave", "", "Yolka (Christmas Tree)"),
        ("Black Burn Black Currant – 100g", "Black Burn", "", "Black Currant"),
    ],
)
def test_extract_flavor(raw, brand, line, name):
    assert extract_flavor(raw, brand, line, LINES.get(brand, set())).name == name


def test_extract_keeps_full_name_variant_for_line_words():
    f = extract_flavor("SEVERNYI TOBACCO SORBET – “Watermelon Sorbet” 100G", "Severnyi", "Sorbet", LINES["Severnyi"])
    assert f.name == "Watermelon"
    assert any(norm(v) == "watermelon sorbet" for v in f.variants)


def test_ingredient_notes_are_split_off():
    f = extract_flavor("Black Burn HiT – Caribbean Heavy 30G (Rum, Lemon, Lime)", "Black Burn", "HiT", {"HiT"})
    assert f.name == "Caribbean Heavy"
    assert f.notes == "Rum, Lemon, Lime"


@pytest.mark.parametrize("text, g", [("Adalya Peach – 250G", 250), ("Al Fakher Mint 1kg", 1000), ("Kraken 100 GR", 100), ("Sarma Free Can", None)])
def test_grams(text, g):
    assert grams(text) == g


def test_display_case():
    assert display_case("DARK SPIRIT") == "Dark Spirit"
    assert display_case("MeJuMi") == "MeJuMi"
    assert display_case("MJ 2.0") == "MJ 2.0"


def test_taxonomy_brand_and_line():
    cats = [
        {"id": 91, "parent": 0, "slug": "tobacco", "name": "Hookah Tobacco"},
        {"id": 93, "parent": 91, "slug": "russian-tobacco", "name": "Russian Hookah Tobacco"},
        {"id": 452, "parent": 93, "slug": "darkside", "name": "DarkSide"},
        {"id": 446, "parent": 452, "slug": "darkside-200", "name": "Darkside 200g"},
        {"id": 448, "parent": 446, "slug": "darkside-200g-core", "name": "Darkside 200g Core"},
        {"id": 504, "parent": 446, "slug": "darkside-shake", "name": "Darkside Shake 200G BASE"},
        {"id": 113, "parent": 91, "slug": "tangiers-tobacco", "name": "Tangiers Tobacco"},
        {"id": 229, "parent": 113, "slug": "tangiers-noir-100gr", "name": "Tangiers Noir 100gr"},
        {"id": 84, "parent": 0, "slug": "sale", "name": "Sale"},
    ]
    t = Taxonomy.build(cats)
    assert t.classify([446, 448]) == ("Darkside", "Core", True, "Darkside 200g Core")
    assert t.classify([446, 504])[:2] == ("Darkside", "Base")
    assert t.classify([84, 229]) == ("Tangiers", "Noir", False, "Tangiers Noir 100gr")
    assert t.classify([84]) is None
