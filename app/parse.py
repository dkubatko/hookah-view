"""Turn raw WHM products into (brand, line, flavor, grams) records."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app import rules
from app.text import clean, display_case, norm

_WEIGHT = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(kg|kgs|grams?|gr|g)\b\.?", re.I)
_CATALOG_NO = re.compile(r"#\s*\d+\w*|\bTC\s*\d+\b")
_PAREN = re.compile(r"\(([^()]*)\)")
_PAREN_NOISE = re.compile(r"#|\bline\b|package|\bnew\b|limited|\btc\s*\d|^\s*\d+\s*(g|gr|kg)\b", re.I)
_SEPARATORS = {"-", "|", ":", ",", "/", "+"}


def grams(text: str) -> int | None:
    m = _WEIGHT.search(text or "")
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    return int(round(value * (1000 if m.group(2).lower().startswith("kg") else 1)))


def _strip_weight(s: str) -> str:
    return _WEIGHT.sub(" ", s)


@dataclass
class Taxonomy:
    """WHM category tree -> brand/line lookup."""

    by_id: dict[int, dict]
    brand_of: dict[int, str] = field(default_factory=dict)
    line_of: dict[int, str] = field(default_factory=dict)
    depth: dict[int, int] = field(default_factory=dict)
    russian: set[int] = field(default_factory=set)
    lines_by_brand: dict[str, set[str]] = field(default_factory=dict)
    brand_categories: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def build(cls, categories: list[dict]) -> Taxonomy:
        t = cls(by_id={c["id"]: c for c in categories})
        for c in categories:
            chain = t._chain(c["id"])  # root .. c
            if not chain or chain[0] != rules.TOBACCO_ROOT or len(chain) < 2:
                continue
            path = chain[1:]
            if path[0] == rules.RUSSIAN_GROUP:
                path = path[1:]
                t.russian.add(c["id"])
            if not path:
                continue
            brand_cat = t.by_id[path[0]]
            brand = rules.BRAND_NAMES.get(brand_cat["slug"]) or _brand_from_category(brand_cat["name"])
            t.brand_of[c["id"]] = brand
            t.depth[c["id"]] = len(path)
            t.brand_categories.setdefault(brand, []).append(brand_cat["name"])
        for cid, brand in t.brand_of.items():
            slug = t.by_id[cid]["slug"]
            if slug in rules.LINE_NAMES:
                line = rules.LINE_NAMES[slug]
            elif t.depth[cid] == 1:
                line = ""
            else:
                line = _line_from_category(t.by_id[cid]["name"], brand, t.brand_categories[brand])
            t.line_of[cid] = line
            if line:
                t.lines_by_brand.setdefault(brand, set()).add(line)
        return t

    def _chain(self, cid: int) -> list[int]:
        out: list[int] = []
        seen = set()
        while cid and cid in self.by_id and cid not in seen:
            seen.add(cid)
            out.append(cid)
            cid = self.by_id[cid]["parent"]
        return out[::-1]

    def classify(self, category_ids: list[int]) -> tuple[str, str, bool, str] | None:
        """(brand, line, russian, deepest category name) for a product."""
        known = [c for c in category_ids if c in self.brand_of]
        known = [c for c in known if self.by_id[c]["slug"] not in rules.IGNORED_CATEGORIES]
        if not known:
            return None
        deepest = max(known, key=lambda c: self.depth[c])
        brand = self.brand_of[deepest]
        # A product can sit in a parent and a child category; the most
        # specific non-empty line wins.
        line = next(
            (self.line_of[c] for c in sorted(known, key=lambda c: -self.depth[c]) if self.line_of[c]),
            "",
        )
        russian = any(c in self.russian for c in known)
        return brand, line, russian, self.by_id[deepest]["name"]


def _words(s: str) -> list[str]:
    return [w for w in re.split(r"\s+", s) if w]


def _brand_from_category(name: str) -> str:
    words = [w for w in _words(_strip_weight(clean(name))) if norm(w) not in rules.GENERIC_NOISE]
    return display_case(" ".join(words)) or clean(name)


def _line_from_category(name: str, brand: str, brand_cat_names: list[str]) -> str:
    drop = {norm(brand)} | {norm(n) for n in brand_cat_names}
    brand_words = set(norm(brand).split())
    for n in brand_cat_names:
        brand_words |= set(norm(_strip_weight(n)).split())
    tokens = _words(_strip_weight(clean(name)).replace(",", " "))

    def is_brandish(w: str) -> bool:
        # "Trofimoff Terror" under brand "Trofimoff's": prefixes count too.
        return any(len(w) >= 4 and (b.startswith(w) or w.startswith(b)) for b in brand_words)

    kept = [
        w for w in tokens
        if norm(w)
        and norm(w) not in rules.GENERIC_NOISE
        and norm(w) not in brand_words
        and norm(w) not in drop
        and not is_brandish(norm(w))
    ]
    return display_case(" ".join(kept))


@dataclass
class Flavor:
    name: str          # display name
    key: str           # normalised grouping key
    variants: list[str]
    notes: str = ""
    line: str = ""     # line implied by the name (rules.name_lines)


def _phrases(*groups) -> set[str]:
    out = set()
    for g in groups:
        for p in g:
            n = norm(p)
            if n:
                out.add(n)
    return out


def extract_flavor(raw: str, brand: str, line: str, brand_lines: set[str]) -> Flavor:
    r = rules.brand_rules(brand)
    s = clean(raw)
    if "|" in s:  # Trifecta: "Trifecta Tobacco 250G Blonde | Cherry Berry"
        s = s.split("|", 1)[1]

    brand_phrases = _phrases([brand], r.get("aliases", []))
    line_phrases = _phrases(brand_lines, [line], r.get("noise", []))
    noise = brand_phrases | line_phrases | rules.GENERIC_NOISE

    aliases: list[str] = []
    notes = ""
    for inner in _PAREN.findall(s):
        inner_n = norm(inner)
        if not inner_n or _PAREN_NOISE.search(inner) or inner_n in noise or all(w in noise for w in inner_n.split()):
            continue
        if "," in inner:
            notes = clean(inner)
        else:
            aliases.append(clean(inner))
    s = _PAREN.sub(" ", s)
    s = _CATALOG_NO.sub(" ", _strip_weight(s))
    s = s.replace('"', " ").replace("–", "-")
    s = re.sub(r"(?<=\s)-|-(?=\s)", " - ", s)
    tokens = _words(s)

    def strip(tokens: list[str], phrases: set[str]) -> list[str]:
        changed = True
        while changed and tokens:
            changed = False
            while tokens and (tokens[0] in _SEPARATORS or not norm(tokens[0])):
                tokens = tokens[1:]
                changed = True
            while tokens and (tokens[-1] in _SEPARATORS or not norm(tokens[-1])):
                tokens = tokens[:-1]
                changed = True
            for k in range(min(4, len(tokens) - 1), 0, -1):
                if norm(" ".join(tokens[:k])) in phrases:
                    tokens = tokens[k:]
                    changed = True
                    break
                if norm(" ".join(tokens[-k:])) in phrases:
                    tokens = tokens[:-k]
                    changed = True
                    break
        return tokens

    # Brand first (so "Black Burn Black Currant" keeps "Black"), then lines.
    tokens = strip(tokens, brand_phrases)
    # Variant that keeps a trailing line word: Severnyi "Watermelon Sorbet"
    # is reviewed under that full name in the Sorbet line.
    lead_only = list(tokens)
    while len(lead_only) > 1 and (lead_only[0] in _SEPARATORS or norm(lead_only[0]) in noise or not norm(lead_only[0])):
        lead_only = lead_only[1:]
    tokens = strip(tokens, noise)

    name_line = ""
    for word, ln in (r.get("name_lines") or {}).items():
        if len(tokens) > 1 and norm(tokens[0]) == norm(word):
            tokens = tokens[1:]
            name_line = ln
            break

    base = " ".join(t for t in tokens if t not in _SEPARATORS).strip(" -")
    base = re.sub(r"\s+", " ", base) or clean(raw)
    display = display_case(base)
    if aliases:
        display = f"{display} ({display_case(aliases[0])})"
    variants = [base] + [f"{base} {a}" for a in aliases] + aliases
    full = " ".join(t for t in lead_only if t not in _SEPARATORS).strip(" -")
    if full and norm(full) != norm(base):
        variants.append(full)
    return Flavor(name=display, key=norm(base), variants=variants, notes=notes, line=name_line)
