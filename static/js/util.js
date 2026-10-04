// Small DOM + formatting helpers shared by every module.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);

export const icon = (name, cls = "") => `<svg class="ico ${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

export const money = (n) =>
  n == null ? "—" : "$" + (n >= 100 || Number.isInteger(n) ? n.toFixed(0) : n.toFixed(2));

export const weight = (g) => (g == null ? "" : g >= 1000 ? `${+(g / 1000).toFixed(2)}kg` : `${g}g`);

export const per100 = (ppg) => (ppg == null ? "" : `${money(ppg * 100)}/100g`);

export const plural = (n, one, many = one + "s") => `${n.toLocaleString()} ${n === 1 ? one : many}`;

// Colour bands for the score (top ~5% green, top ~25% light green, …).
export function ratingColor(r) {
  if (r == null) return "var(--muted)";
  if (r >= 4.35) return "var(--r5)";
  if (r >= 4.1) return "var(--r4)";
  if (r >= 3.85) return "var(--r3)";
  if (r >= 3.5) return "var(--r2)";
  return "var(--r1)";
}

export function ago(ts) {
  if (!ts) return "never";
  const s = Date.now() / 1000 - ts;
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400 * 2) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} days ago`;
}

export function debounce(fn, ms) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

let toastTimer;
export function toast(msg, ms = 2400) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), ms);
}

// Search normalisation: lowercase, ё→е, strip accents and punctuation.
export const fold = (s) =>
  String(s || "")
    .toLowerCase()
    .replace(/ё/g, "е")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
