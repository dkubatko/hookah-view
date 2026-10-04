"""Match shop flavors (WHM) to reviewed flavors (HTR).

Each HTR flavor gets several English candidate strings: its Latin name and
alt name, Latin text in parentheses, every ModernMT translation of a Russian
name, a transliteration, and the URL slug (itself a transliteration).  Each
shop flavor is scored against every candidate of its brand with a
coverage-aware fuzzy score:

    char     = best of ratio / token_sort / token_set / spaceless ratio
    coverage = min(share of shop words found in HTR, share of HTR words found in shop)
    score    = char * (0.35 + 0.65 * coverage)

Requiring coverage in both directions stops one shared word from carrying
a match ("Mango Tango" vs "Ekzo Mango").  Line affinity then nudges the
result: an HTR flavor from the same product line gets a bonus, one from a
different, known line a penalty, so "Pear" in Darkside Base doesn't land on
"Pear" in Darkside Core when both exist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from app import translate
from app.text import fix_homoglyphs, has_cyrillic, is_mostly_latin, norm, translit

THRESHOLD = 72
SAME_LINE_BONUS = 4
OTHER_LINE_PENALTY = 6
STOP = {"and", "with", "the", "of", "a", "de", "la", "al", "el", "il", "le", "di", "i", "o", "s", "n", "x"}


# Less trustworthy candidate strings carry a small handicap, so an exact hit
# on a flavor's real name beats an exact hit on another flavor's alternate
# machine translation ("Strawberry": клубника, not земляника).
EXACT, TRANSLATION, ALT_TRANSLATION, TRANSLIT = 0, 1, 4, 3


@dataclass(slots=True)
class Candidate:
    item: dict
    strings: list[tuple[str, int]]
    line_slug: str


@dataclass
class BrandIndex:
    candidates: list[Candidate]
    flat: list[str] = field(default_factory=list)
    penalty: list[int] = field(default_factory=list)
    owner: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        for i, c in enumerate(self.candidates):
            for s, pen in c.strings:
                self.flat.append(s)
                self.penalty.append(pen)
                self.owner.append(i)


def _latin_parens(s: str) -> list[str]:
    return [m for m in re.findall(r"\(([^()]+)\)", s) if is_mostly_latin(m)]


def candidate_strings(
    item: dict, brand_words: set[str], line_words: set[str], suffixes: set[str] = frozenset()
) -> list[tuple[str, int]]:
    name = fix_homoglyphs(item.get("name", ""))
    alt = fix_homoglyphs(item.get("alt_name", ""))
    raw: list[tuple[str, int]] = []
    latin = [s for s in (name, alt) if s and is_mostly_latin(s)]
    raw += [(s, EXACT) for s in latin]
    # Renamed flavors keep the old name as "ex. White Strawberry".
    raw += [(m.group(1), EXACT) for s in latin if (m := re.match(r"(?i)^(?:ex|formerly)\.?\s+(.+)", s))]
    raw += [(s, EXACT) for s in _latin_parens(name) + _latin_parens(alt)]
    russian = [s for s in (name, alt) if s and has_cyrillic(s) and not is_mostly_latin(s)]
    # A Russian name always gets translated: when the alt name is Latin it is
    # often a marketing name ("Арбуз и дыня" / "Wonder melon").  A Russian alt
    # name next to a Latin name is just its translation - skip it.
    for s in russian:
        if s == name or not latin:
            for i, t in enumerate(translate.lookup(s)[:6]):
                raw.append((t, TRANSLATION if i == 0 else ALT_TRANSLATION))
    for s in russian[:1]:
        raw.append((translit(s), TRANSLIT))
    slug_tail = item.get("slug", "").rsplit("/", 1)[-1]
    raw.append((slug_tail.replace("-", " "), TRANSLIT))

    best: dict[str, int] = {}
    for s, pen in raw:
        n = norm(s)
        words = n.split()
        # "Darkside Cola" -> "Cola"; "Sambuka Shot" (Shot line) -> "Sambuka"
        while len(words) > 1 and words[0] in brand_words:
            words = words[1:]
        trimmed = list(words)
        while len(trimmed) > 1 and (trimmed[-1] in line_words or trimmed[-1] in suffixes):
            trimmed.pop()
        for v in (n, " ".join(words), " ".join(trimmed)):
            if v and pen < best.get(v, 99):
                best[v] = pen
    return list(best.items())


def build_index(items: list[dict], brand_names: list[str], suffixes: list[str] = ()) -> BrandIndex:
    brand_words = {w for b in brand_names for w in norm(b).split()}
    trim = {norm(x) for x in suffixes}

    def own_line_words(it: dict) -> set[str]:
        text = f"{it.get('line', '')} {it.get('line_slug', '').replace('-', ' ')}"
        return {w for w in norm(text).split() if len(w) > 2 and w not in brand_words and w != "main"}

    return BrandIndex(
        [
            Candidate(it, candidate_strings(it, brand_words, own_line_words(it), trim), it.get("line_slug", ""))
            for it in items
        ]
    )


def _token_hit(tok: str, others: set[str], collapsed: str) -> float:
    if tok in others:
        return 1.0
    if len(tok) >= 4:
        for o in others:
            if len(o) >= 4 and (tok in o or o in tok):
                return 0.85
        for o in others:
            if len(o) >= 4 and fuzz.ratio(tok, o) >= 75:  # gray/grey, gummy/gummi
                return 0.85
        if tok in collapsed:
            return 0.75
    return 0.0


def score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a.replace(" ", "") == b.replace(" ", ""):  # "Bubblegum" / "Bubble Gum"
        return 100.0
    char = max(
        fuzz.ratio(a, b),
        fuzz.token_sort_ratio(a, b),
        fuzz.token_set_ratio(a, b),
        fuzz.ratio(a.replace(" ", ""), b.replace(" ", "")),
    )
    wa = {t for t in a.split() if t not in STOP}
    wb = {t for t in b.split() if t not in STOP}
    if not wa or not wb:
        return char
    if len(wa) == 1 and len(wb) == 1 and char >= 85:
        return char
    hit_a = sum(_token_hit(t, wb, b.replace(" ", "")) for t in wa) / len(wa)
    hit_b = sum(_token_hit(t, wa, a.replace(" ", "")) for t in wb) / len(wb)
    coverage = min(hit_a, hit_b)
    if coverage == 0:
        return 0.0
    return char * (0.35 + 0.65 * coverage)


@dataclass(slots=True)
class Result:
    item: dict | None
    score: float
    runner_up: float = 0.0


def best_match(
    variants: list[str],
    index: BrandIndex,
    line_slugs: set[str] | None,
    exclude: set[int] = frozenset(),
    top_k: int = 15,
) -> Result:
    queries = [q for q in dict.fromkeys(norm(v) for v in variants) if q]
    if not queries or not index.flat:
        return Result(None, 0.0)
    best: dict[int, float] = {}
    for q in queries:
        # Cheap prefilters in C, then the precise score on the survivors.
        # token_set alone saturates at 100 for every name containing the
        # query ("Cherry" vs "Cherry Sangria"), so token_sort runs too.
        survivors = {
            j
            for scorer in (fuzz.token_set_ratio, fuzz.token_sort_ratio)
            for _s, _score, j in process.extract(q, index.flat, scorer=scorer, limit=top_k)
        }
        for j in survivors:
            ci = index.owner[j]
            if index.candidates[ci].item["id"] in exclude:
                continue
            s = score(q, index.flat[j]) - index.penalty[j]
            if s > best.get(ci, 0.0):
                best[ci] = s
    if not best:
        return Result(None, 0.0)

    def adjusted(ci: int) -> tuple[float, int, int]:
        c = index.candidates[ci]
        s = best[ci]
        if line_slugs:
            s += SAME_LINE_BONUS if c.line_slug in line_slugs else -OTHER_LINE_PENALTY
        in_production = 0 if c.item.get("status") == "Снят с производства" else 1
        return (s, in_production, c.item.get("ratings") or 0)

    ranked = sorted(best, key=adjusted, reverse=True)
    top_score = adjusted(ranked[0])[0]
    runner = adjusted(ranked[1])[0] if len(ranked) > 1 else 0.0
    if top_score < THRESHOLD:
        return Result(None, top_score, runner)
    return Result(index.candidates[ranked[0]].item, min(100.0, top_score), runner)
