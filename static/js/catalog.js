// Catalog data: loading, derived fields, filtering, sorting, facet counts.
import { fold } from "./util.js";

export const SORTS = [
  ["best", "Best rated"],
  ["popular", "Most rated"],
  ["value", "Price per 100g"],
  ["price", "Lowest price"],
  ["new", "Newest"],
  ["name", "Name A–Z"],
];

export const STRENGTHS = ["Light", "Medium-light", "Medium", "Medium-strong", "Strong"];

export const PACKS = [
  ["s", "Sample ≤50g", (g) => g && g <= 50],
  ["m", "100–125g", (g) => g > 50 && g <= 150],
  ["l", "200–250g", (g) => g > 150 && g <= 300],
  ["xl", "1kg", (g) => g > 300],
];

// Steps for the score filter (the score is the HTReviews average adjusted
// for how many people rated it; see build.py).
export const RATING_STEPS = [0, 4, 4.2, 4.3, 4.4, 4.5];
export const COUNT_STEPS = [0, 5, 10, 20, 50, 100];
export const NEW_DAYS = 14;
export const BACK_DAYS = 7;
export const APPROX = 84; // match scores below this are flagged "approximate"

export let DATA = null; // { products, brands, groups, tag_group, stats, built }

export async function load({ fresh = false } = {}) {
  // index.html starts this request before the modules load.
  const early = !fresh && window.__catalog;
  window.__catalog = null;
  const r = early ? await early : await fetch("/api/catalog", fresh ? { cache: "no-cache" } : {});
  if (r.status === 503) return null;
  if (!r.ok) throw new Error(`catalog: HTTP ${r.status}`);
  const data = await r.json();
  prepare(data);
  DATA = data;
  return data;
}

function prepare(data) {
  const colors = Object.fromEntries(data.groups.map((g) => [g.key, g.color]));
  data.groupColor = colors;
  const now = Date.now() / 1000;
  data.bySku = new Map();
  data.byKey = new Map();
  for (const p of data.products) {
    const h = p.h;
    p.groups = new Set(h ? h.tags.map((t) => data.tag_group[t]).filter(Boolean) : []);
    p.newest = Math.max(...p.s.map((s) => s.id));
    p.isNew = !!p.new && now - p.new < NEW_DAYS * 86400;
    p.isBack = !!p.back && now - p.back < BACK_DAYS * 86400 && p.stock;
    p.approx = !!h && !p.mo && p.ms < APPROX;
    p.hay = fold(
      [p.n, p.b, p.l, p.nt, h?.n, h?.ru, h?.line, ...(h?.tags || []), ...p.groups].join(" "),
    );
    p.title = ` ${fold([p.n, p.b, h?.n, h?.ru].join(" "))} `;
    data.byKey.set(p.k, p);
    for (const k of p.keys || []) data.byKey.set(k, p);
    for (const s of p.s) data.bySku.set(s.id, { p, s });
  }
}

export function defaults() {
  return {
    q: "",
    stock: true,
    brands: new Set(), // "Brand" or "Brand\u0001Line"
    groups: new Set(),
    strength: new Set(),
    packs: new Set(),
    rmin: 0,
    rcmin: 0,
    isNew: false,
    isBack: false,
    origin: "", // "", "ru", "other"
    rated: "", // "", "rated", "unrated", "review"
    sort: "best",
  };
}

const brandMatch = (f, p) => {
  if (!f.brands.size) return true;
  return f.brands.has(p.b) || f.brands.has(`${p.b}\u0001${p.l}`);
};

// Each predicate can be skipped so facet counts show "what you'd get if
// you toggled this one".
const PREDICATES = {
  q: (f, p, terms) => terms.every((t) => p.hay.includes(t)),
  stock: (f, p) => !f.stock || p.stock,
  brands: brandMatch,
  groups: (f, p) => !f.groups.size || [...f.groups].some((g) => p.groups.has(g)),
  strength: (f, p) => !f.strength.size || (p.h && f.strength.has(p.h.st)),
  packs: (f, p) => {
    if (!f.packs.size) return true;
    const sizes = f.stock ? p.s.filter((s) => s.st) : p.s;
    return PACKS.some(([k, , test]) => f.packs.has(k) && sizes.some((s) => test(s.g)));
  },
  rmin: (f, p) => !f.rmin || (p.score ?? 0) >= f.rmin,
  rcmin: (f, p) => !f.rcmin || (p.h?.rc ?? 0) >= f.rcmin,
  isNew: (f, p) => !f.isNew || p.isNew,
  isBack: (f, p) => !f.isBack || p.isBack,
  origin: (f, p) => !f.origin || (f.origin === "ru") === p.ru,
  rated: (f, p) => {
    if (!f.rated) return true;
    if (f.rated === "rated") return !!p.h?.r;
    if (f.rated === "unrated") return !p.h;
    return (!p.h && DATA.brands[p.b]?.htr) || p.approx; // "review": needs a human look
  },
};

export function filter(f, skip = null) {
  const terms = fold(f.q).split(" ").filter(Boolean);
  const preds = Object.entries(PREDICATES).filter(([k]) => k !== skip);
  return DATA.products.filter((p) => preds.every(([, fn]) => fn(f, p, terms)));
}

const byName = (a, b) => a.n.localeCompare(b.n);
const nullsLast = (v) => (v == null ? -Infinity : v);

// Search relevance: whole words in the name/brand beat word prefixes, which
// beat matches anywhere else ("grape" ranks Grape Mint above Grapefruit).
export function relevance(p, terms) {
  if (terms.every((t) => p.title.includes(` ${t} `))) return 3;
  if (terms.every((t) => p.title.includes(` ${t}`))) return 2;
  return 1;
}

export function sort(list, how, q = "") {
  const terms = fold(q).split(" ").filter(Boolean);
  if (terms.length) for (const p of list) p.rel = relevance(p, terms);
  const cmp = {
    best: (a, b) => nullsLast(b.score) - nullsLast(a.score) || (b.h?.rc ?? 0) - (a.h?.rc ?? 0),
    popular: (a, b) => (b.h?.rc ?? -1) - (a.h?.rc ?? -1),
    value: (a, b) => (a.ppg ?? 1e9) - (b.ppg ?? 1e9),
    price: (a, b) => a.pmin - b.pmin,
    new: (a, b) => b.newest - a.newest,
    name: byName,
  }[how] || (() => 0);
  if (terms.length) return list.sort((a, b) => b.rel - a.rel || cmp(a, b) || byName(a, b));
  return list.sort((a, b) => cmp(a, b) || byName(a, b));
}

export function counts(f, key, keyOf) {
  const out = new Map();
  for (const p of filter(f, key)) {
    for (const k of keyOf(p)) out.set(k, (out.get(k) || 0) + 1);
  }
  return out;
}

// Filters without their own quick chip (the sliders button shows this count).
export const activeCount = (f) => f.strength.size + f.packs.size + (f.origin === "other" ? 1 : 0) + (f.rated ? 1 : 0);

export const anyActive = (f) =>
  !!(f.q || f.brands.size || f.groups.size || f.strength.size || f.packs.size || f.rmin || f.rcmin || f.isNew || f.isBack || f.origin || f.rated);

// Stock and origin are sticky between visits (e.g. "always Russian only").
const PREFS = "hs_prefs_v2";
export function savePrefs(f) {
  localStorage.setItem(PREFS, JSON.stringify({ stock: f.stock, origin: f.origin }));
}
export function loadPrefs(f) {
  try {
    const p = JSON.parse(localStorage.getItem(PREFS) || "{}");
    if (typeof p.stock === "boolean") f.stock = p.stock;
    if (["", "ru", "other"].includes(p.origin)) f.origin = p.origin;
  } catch {
    /* ignore */
  }
  return f;
}

// ── URL <-> filters ────────────────────────────────────────────────────
export function toQuery(f) {
  const d = defaults();
  const q = new URLSearchParams();
  if (f.q) q.set("q", f.q);
  if (f.stock !== d.stock) q.set("stock", f.stock ? "1" : "0");
  if (f.brands.size) q.set("brand", [...f.brands].map((b) => b.replace("\u0001", "~")).join(","));
  if (f.groups.size) q.set("flavor", [...f.groups].join(","));
  if (f.strength.size) q.set("strength", [...f.strength].join(","));
  if (f.packs.size) q.set("pack", [...f.packs].join(","));
  if (f.rmin) q.set("rating", f.rmin);
  if (f.rcmin) q.set("ratings", f.rcmin);
  if (f.isNew) q.set("new", "1");
  if (f.isBack) q.set("back", "1");
  if (f.origin) q.set("origin", f.origin);
  if (f.rated) q.set("rated", f.rated);
  if (f.sort !== d.sort) q.set("sort", f.sort);
  return q.toString();
}

export function fromQuery(search) {
  const q = new URLSearchParams(search);
  const f = defaults();
  const list = (k) => (q.get(k) || "").split(",").filter(Boolean);
  if (q.has("q")) f.q = q.get("q");
  if (q.has("stock")) f.stock = q.get("stock") === "1";
  f.brands = new Set(list("brand").map((b) => b.replace("~", "\u0001")));
  f.groups = new Set(list("flavor"));
  f.strength = new Set(list("strength").map(Number));
  f.packs = new Set(list("pack"));
  f.rmin = +q.get("rating") || 0;
  f.rcmin = +q.get("ratings") || 0;
  f.isNew = q.get("new") === "1";
  f.isBack = q.get("back") === "1";
  f.origin = q.get("origin") || "";
  f.rated = q.get("rated") || "";
  if (SORTS.some(([k]) => k === q.get("sort"))) f.sort = q.get("sort");
  return f;
}
