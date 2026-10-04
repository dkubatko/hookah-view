"""Shop-specific knowledge that can't be derived automatically.

Brands and lines are derived from WHM's category tree (Hookah Tobacco >
[Russian Hookah Tobacco >] Brand > Line/size).  This file only holds the
exceptions: display names, HTR slugs that differ from the brand name, line
labels WHM spells oddly, and HTR line slugs that are in Russian.

New brands or lines on WHM work without touching this file; add an entry
only when the automatic result looks wrong.
"""
from __future__ import annotations

TOBACCO_ROOT = 91       # "Hookah Tobacco"
RUSSIAN_GROUP = 93      # "Russian Hookah Tobacco" - groups brands, isn't one
IGNORED_CATEGORIES = {"sale", "uncategorized"}

# Brand-level WHM category slug -> display name (when the cleaned category
# name isn't right).
BRAND_NAMES = {
    "al-fakher-tobacco": "Al Fakher",
    "blackburn": "Black Burn",
    "darkside": "Darkside",
    "eternal-smoke": "Eternal Smoke",
    "musthave-tobacco-russian-tobacco": "MustHave",
}

# WHM sub-category slug -> line label ("" = the brand's main line).
LINE_NAMES = {
    "darkside-200": "",
    "darkside-shake": "Base",
    "darkside-xperience": "Xperience",
    "darkside-shots-30gr": "Shot",
    "darkside-shot-125gr": "Shot",
    "kraken-cigar-for-hookah": "Cigar for Hookah",
    "kraken-line-pro-fumelier-30": "Pro Fumelier",
    "100-gr": "Pro Fumelier",
    "fumari-250g": "50/50",
    "al-fakher-x-cookies": "Cookies",
    "al-fakher-snoop-dogg": "Snoop Dogg",
    "severnyi-classic": "",
    "tangiers-f-line-100": "F-Line",
    "tangiers-f-line-250": "F-Line",
}


class Brand(dict):
    """Per-brand overrides, all optional:

    htr       HTR brand slug; None = brand isn't on HTR (skip the lookup)
    aliases   other spellings used at the start of WHM product names
    noise     words to drop from WHM product names
    lines     WHM line label -> HTR line slugs (after "brand/")
    name_lines  leading words in a product name that name its HTR line
    htr_suffixes  trailing words of HTR names that WHM leaves out
    """


BRANDS: dict[str, Brand] = {
    # Shot flavors: WHM "Caspian" = HTR "Каспийский вайб" (Caspian vibe).
    "Darkside": Brand(htr_suffixes=["vibe", "chill", "punch", "shake", "beat", "trip", "crash", "vayb", "panch", "sheyk", "bit", "krash"]),
    "Element": Brand(lines={"Air": ["vozdukh"], "Earth": ["zemlya"], "Water": ["voda"], "V": ["v-element"]}),
    "Eternal Smoke": Brand(aliases=["Eternal"]),
    "Sarma": Brand(lines={"Classic": ["klassicheskaya"], "Hard": ["krepkaya-sarma-360"], "Soft": ["legkaya-sarma-360"]}),
    "Severnyi": Brand(htr="severnyy"),
    "Starbuzz": Brand(noise=["Exotic"]),
    "Chabacco": Brand(name_lines={"Mix": "Mix", "Emotions": "Emotions"}),
    "Bonche": Brand(name_lines={"Bartender": "Bartender"}, noise=["Limited Edition"]),
    # Not reviewed on HTR (checked 2026-10).
    "HJ Uncut": Brand(htr=None),
    "Kartel": Brand(htr=None),
    "Platinum Seven": Brand(htr=None),
}


def brand_rules(brand: str) -> Brand:
    return BRANDS.get(brand, Brand())


# Words that never belong to a flavor name.
GENERIC_NOISE = {"tobacco", "hookah", "line", "collection", "shisha", "molasses"}
