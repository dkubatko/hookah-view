"""String helpers shared by the catalog builder and the matcher."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_CYRILLIC = re.compile(r"[а-яё]", re.I)

# Cyrillic look-alikes that sneak into Latin names ("Nаш", "Сinnamon").
_HOMOGLYPHS = str.maketrans("АВЕКМНОРСТХаеорсухі", "ABEKMHOPCTXaeopcyxi")

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def has_cyrillic(s: str) -> bool:
    return bool(_CYRILLIC.search(s or ""))


def is_mostly_latin(s: str) -> bool:
    """True when a string reads as Latin text (homoglyphs aside)."""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if _CYRILLIC.match(c))
    return cyr <= 1 and len(letters) - cyr >= 2


def fix_homoglyphs(s: str) -> str:
    """Replace stray Cyrillic letters inside otherwise-Latin words."""
    if not s or not is_mostly_latin(s):
        return s
    return s.translate(_HOMOGLYPHS)


def translit(s: str) -> str:
    return "".join(_TRANSLIT.get(c, _TRANSLIT.get(c.lower(), c)) for c in s.lower())


@lru_cache(maxsize=100_000)
def clean(s: str) -> str:
    """Unicode tidy-up: NFKC, straight quotes, ASCII dashes, no ®/™."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[​-‏﻿]", "", s)
    s = re.sub(r"[‐-―−]", "-", s)
    s = re.sub(r"[‘’ʼ`´]", "'", s)
    s = re.sub(r"[“”«»]", '"', s)
    s = re.sub(r"[®™©]", "", s)
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=200_000)
def norm(s: str) -> str:
    """Matching key: lowercase alnum words, versions like 2.0 -> 20."""
    s = clean(fix_homoglyphs(s)).lower().replace("ё", "е")
    s = s.replace("&", " and ")
    s = re.sub(r"(\d)[.,](\d)", r"\1\2", s)
    s = re.sub(r"'", "", s)
    s = re.sub(r"[^\w]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_KEEP_UPPER = {"HJ", "TC", "XO", "USA", "BBQ", "IPA", "DS", "GFE", "II", "III", "IV", "XL", "MRS", "MR", "DJ", "MJ"}
_SMALL = {"in", "the", "of", "and", "a", "on", "with", "or", "to", "for", "de", "la", "da"}


def display_case(s: str) -> str:
    """Title-case SHOUTED text but leave deliberate casing (MeJuMi) alone."""
    letters = [c for c in s if c.isalpha()]
    shouted = bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.7

    def fix(i: int, word: str) -> str:
        w_letters = [c for c in word if c.isalpha()]
        if not w_letters or word.upper() in _KEEP_UPPER:
            return word
        all_caps = all(c.isupper() for c in w_letters)
        if not (all_caps and (len(w_letters) >= 3 or shouted)):
            return word
        if i > 0 and word.lower() in _SMALL:
            return word.lower()
        return re.sub(r"[^\W\d_]+", lambda m: m.group(0).capitalize(), word.lower())

    out = " ".join(fix(i, w) for i, w in enumerate(s.split(" ")))
    return out[:1].upper() + out[1:] if out[:1].islower() else out


def slugify(s: str) -> str:
    s = translit(clean(s)).lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
