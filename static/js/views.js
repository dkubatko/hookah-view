// HTML builders. Everything here is a pure function of data -> markup;
// event wiring lives in app.js (delegated listeners on stable containers).
import { DATA, PACKS, RATING_STEPS, COUNT_STEPS, STRENGTHS, APPROX, counts } from "./catalog.js";
import { esc, icon, money, weight, per100, ratingColor, plural, ago } from "./util.js";
import * as cart from "./cart.js";

const HTR = "https://htreviews.org/tobaccos/";

const initials = (s) =>
  String(s)
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase();

export const thumb = (p, size = 84) =>
  `<div class="thumb">${
    p.img
      ? `<img src="${esc(p.img)}" alt="" loading="lazy" decoding="async" width="${size}" height="${size}" onerror="this.nextElementSibling.hidden=false;this.remove()">`
      : ""
  }<span class="ph"${p.img ? " hidden" : ""}>${esc(initials(p.n))}</span></div>`;

function ratingBadge(h) {
  if (h?.r != null)
    return `<span class="rating" style="--rc:${ratingColor(h.r)}" title="${h.rc} ratings on HTReviews">${icon("star")}${h.r.toFixed(1)}</span>`;
  return `<span class="rating none">${h ? "No ratings yet" : "Unrated"}</span>`;
}

export function strengthBars(st, label = true) {
  if (!st) return "";
  const bars = [1, 2, 3, 4, 5].map((i) => `<i class="${i <= st ? "on" : ""}"></i>`).join("");
  return `<span class="strength" data-s="${st}" title="Strength: ${STRENGTHS[st - 1]}">${bars}</span>${
    label ? `<span>${STRENGTHS[st - 1]}</span>` : ""
  }`;
}

const tagChip = (t) => `<span class="tag" style="--c:${DATA.groupColor[DATA.tag_group[t]] || "var(--muted)"}">${esc(t)}</span>`;

function flags(p, approx = false) {
  let out = "";
  if (p.isNew) out += `<span class="flag new">New</span>`;
  if (p.isBack) out += `<span class="flag back">Back in stock</span>`;
  if (approx && p.approx) out += `<span class="flag approx" title="Rating matched by a looser name comparison">≈ match</span>`;
  return out;
}

function sizeChip(s) {
  const cls = ["size", s.st ? "" : "out", s.rp ? "sale" : ""].join(" ");
  const was = s.rp ? `<span class="was">${money(s.rp)}</span>` : "";
  return `<span class="${cls}">${s.g ? `<span class="w">${weight(s.g)}</span>` : ""}${money(s.p)}${was}</span>`;
}

export function card(p) {
  const h = p.h;
  const meta = [];
  if (h?.st) meta.push(strengthBars(h.st));
  if (h?.rc) meta.push(`<span>${plural(h.rc, "rating")}</span>`);
  const fl = flags(p, DATA.reviewMode);
  if (fl) meta.push(fl);
  const tags = h?.tags?.length ? `<div class="tags">${h.tags.slice(0, 4).map(tagChip).join("")}</div>` : "";
  const sizes = p.s.slice(0, 5).map(sizeChip).join("");
  const sub = `<b>${esc(p.b)}</b>${p.l ? ` · ${esc(p.l)}` : ""}`;
  return `<article class="card${p.stock ? "" : " oos"}" data-k="${esc(p.k)}" tabindex="0" role="button">
  ${thumb(p)}
  <div class="card-body">
    <div class="card-title"><h3 class="name">${esc(p.n)}</h3>${ratingBadge(h)}</div>
    <div class="line2"><div class="sub">${sub}</div>
    ${meta.length ? `<div class="meta">${meta.join('<span class="sep">·</span>')}</div>` : ""}</div>
    ${tags}
    <div class="sizes">${sizes}</div>
  </div>
  <div class="card-desk">${h?.tags?.length ? `<div class="tags">${h.tags.slice(0, 3).map(tagChip).join("")}</div>` : ""}</div>
  <div class="list-right">${ratingBadge(h)}<span class="price">${p.stock ? "" : "<small>sold out · </small>"}${money(p.pmin)}${
    p.ppg ? ` <small>${per100(p.ppg)}</small>` : ""
  }</span></div>
</article>`;
}

export const skeleton = (n = 8) =>
  Array.from({ length: n }, () =>
    `<div class="card skel"><div class="thumb"></div><div class="card-body"><div class="bar" style="width:60%"></div><div class="bar" style="width:35%"></div><div class="bar" style="width:80%"></div></div></div>`,
  ).join("");

// ── detail ─────────────────────────────────────────────────────────────
function stars(r) {
  return [1, 2, 3, 4, 5]
    .map((i) => `<span class="${r >= i - 0.25 ? "" : "off"}">${icon("star")}</span>`)
    .join("");
}

export function detail(p) {
  const h = p.h;
  const rc = ratingColor(h?.r);
  const sizes = p.s
    .map((s) => {
      const inList = cart.qtyOf(s.id);
      return `<div class="d-size">
      <div class="l"><b>${weight(s.g) || "—"}</b> · <b>${money(s.p)}</b>${s.rp ? ` <s class="hint">${money(s.rp)}</s>` : ""}
        <small><span class="${s.st ? "stock-in" : "stock-out"}">${s.st ? "In stock" : "Sold out"}</span>${s.g ? ` · ${per100(s.p / s.g)}` : ""}</small></div>
      <div class="r">
        <a class="btn sm ghost" href="${esc(s.u)}" target="_blank" rel="noopener" aria-label="Open ${weight(s.g)} on World Hookah Market">${icon("ext", "sm")}</a>
        <button class="btn sm ${inList ? "" : "primary"}" data-act="add" data-sku="${s.id}" ${s.st ? "" : "disabled"}>
          ${inList ? `${icon("check", "sm")} ${inList} in list` : `${icon("plus", "sm")} Add`}</button>
      </div>
    </div>`;
    })
    .join("");

  let rating;
  if (h) {
    const bayes = p.score != null ? `<small>Confidence-weighted score ${p.score.toFixed(2)}</small>` : "";
    rating = `<div class="d-block">
      <h3>HTReviews rating <a class="linkish" href="${HTR}${esc(h.u)}" target="_blank" rel="noopener">Open ${icon("ext", "xs")}</a></h3>
      ${
        h.r != null
          ? `<div class="d-score" style="--rc:${rc}"><div class="big">${h.r.toFixed(1)}</div><div><div class="stars">${stars(h.r)}</div><small>${plural(h.rc, "rating")} · ${plural(h.rv, "review")}</small>${bayes}</div></div>`
          : `<p class="hint">Listed on HTReviews but nobody has rated it yet.</p>`
      }
      <div class="d-stats">
        <div class="d-stat"><b>${h.st ? STRENGTHS[h.st - 1] : "—"}</b><span>Strength</span></div>
        <div class="d-stat"><b>${esc(h.stat || "—")}</b><span>Status</span></div>
        <div class="d-stat"><b>${esc(h.line || "Main")}</b><span>HTR line</span></div>
      </div>
      ${h.tags.length ? `<div class="tags" style="margin-top:12px">${h.tags.map(tagChip).join("")}</div>` : ""}
    </div>`;
  } else {
    const onHtr = DATA.brands[p.b]?.htr;
    rating = `<div class="d-block"><h3>HTReviews rating</h3><p class="hint">${
      onHtr
        ? "No matching flavor found on HTReviews. If it's there under another name, link it below."
        : `${esc(p.b)} isn't reviewed on HTReviews.`
    }</p></div>`;
  }

  const matchInfo = h
    ? `Rated as <b>${esc(h.n)}</b>${h.ru && h.ru !== h.n ? ` (${esc(h.ru)})` : ""}${h.line && h.line !== p.l ? ` in the ${esc(h.line)} line` : ""}.
       <div class="why">${p.mo ? "Linked by hand." : `Matched automatically by name${p.ms < APPROX ? " — loosely, worth a check" : ""} (${p.ms}%).`}</div>`
    : p.mo
      ? `Marked by hand as not on HTReviews.`
      : `No automatic match.`;

  const brandHtr = DATA.brands[p.b]?.htr;
  return {
    title: "",
    body: `<div class="d-hero">${thumb(p, 112)}<div>
        <h2 id="sheet-title">${esc(p.n)}</h2>
        ${h?.ru && h.ru !== p.n ? `<div class="d-ru">${esc(h.ru)}</div>` : ""}
        <div class="d-sub"><b>${esc(p.b)}</b>${p.l ? `<span>· ${esc(p.l)}</span>` : ""}${DATA.brands[p.b]?.country ? `<span class="hint">· ${esc(DATA.brands[p.b].country)}</span>` : ""}${flags(p, true)}</div>
      </div></div>
      ${p.nt ? `<p class="notes">${esc(p.nt)}</p>` : ""}
      ${rating}
      <div class="d-block"><h3>Sizes at World Hookah Market</h3><div class="d-sizes">${sizes}</div></div>
      ${
        brandHtr
          ? `<div class="d-block"><h3>Rating match <button class="linkish" data-act="fix">${icon("wrench", "xs")} Fix</button></h3><div class="d-match">${matchInfo}</div></div>`
          : ""
      }`,
  };
}

// ── filters ────────────────────────────────────────────────────────────
const chip = (label, attrs, on, extra = "") =>
  `<button type="button" class="chip" aria-pressed="${on}" ${attrs}>${extra}${label}</button>`;
const n = (v) => (v != null ? ` <span class="n">${v}</span>` : "");

export function filters(f, { brandQuery = "", openBrands = new Set() } = {}) {
  const gc = counts(f, "groups", (p) => p.groups);
  const sc = counts(f, "strength", (p) => (p.h?.st ? [p.h.st] : []));
  const pc = counts(f, "packs", (p) => {
    const sizes = f.stock ? p.s.filter((s) => s.st) : p.s;
    return PACKS.filter(([, , t]) => sizes.some((s) => t(s.g))).map(([k]) => k);
  });
  const bc = counts(f, "brands", (p) => [p.b, `${p.b}\u0001${p.l}`]);

  const groups = DATA.groups
    .filter((g) => gc.get(g.key) || f.groups.has(g.key))
    .map((g) => chip(esc(g.key) + n(gc.get(g.key) || 0), `data-f="groups" data-v="${esc(g.key)}"`, f.groups.has(g.key), `<span class="dot" style="--c:${g.color}"></span>`))
    .join("");

  const brandNames = Object.keys(DATA.brands).sort((a, b) => a.localeCompare(b));
  const bq = brandQuery.trim().toLowerCase();
  const brands = brandNames
    .filter((b) => !bq || b.toLowerCase().includes(bq))
    .map((b) => {
      const lines = DATA.brands[b].lines;
      const selLines = lines.filter((l) => f.brands.has(`${b}\u0001${l}`));
      const state = f.brands.has(b) ? "on" : selLines.length ? "part" : "";
      const open = openBrands.has(b) || selLines.length > 0;
      const lineRows =
        lines.length && open
          ? `<div class="lines">${["", ...lines]
              .map((l) => {
                const key = `${b}\u0001${l}`;
                const c = bc.get(key) || 0;
                if (!c && !f.brands.has(key)) return "";
                return `<div class="brow${f.brands.has(key) ? " on" : ""}" data-f="brands" data-v="${esc(key)}" role="checkbox" aria-checked="${f.brands.has(key)}" tabindex="0"><span class="box">${icon("check")}</span><span class="name-col">${l ? esc(l) : "Main line"}</span><span class="n">${c}</span></div>`;
              })
              .join("")}</div>`
          : "";
      const flag = DATA.brands[b].htr ? "" : `<span class="flagtxt" title="Not reviewed on HTReviews">no HTR</span>`;
      return `<div class="brow${state === "on" ? " on" : ""}" data-f="brands" data-v="${esc(b)}" role="checkbox" aria-checked="${state === "on"}" tabindex="0">
          <span class="box ${state}">${state === "on" ? icon("check") : ""}</span>
          <span class="name-col">${esc(b)}</span>${flag}<span class="n">${bc.get(b) || 0}</span>
          ${lines.length ? `<button type="button" class="exp" data-exp="${esc(b)}" aria-expanded="${open}" aria-label="Lines">${icon("chev")}</button>` : ""}
        </div>${lineRows}`;
    })
    .join("");

  const sw = (key, label, hint) =>
    `<label class="switch"><span>${label}${hint ? `<small>${hint}</small>` : ""}</span><input type="checkbox" data-f="${key}" ${f[key] ? "checked" : ""}></label>`;

  return `
  <div class="fsec">
    <h4>Show <button class="linkish" data-act="reset">Reset all</button></h4>
    ${sw("stock", "In stock only")}
    ${sw("isNew", "New arrivals", "Added in the last 14 days")}
    ${sw("isBack", "Back in stock", "Restocked in the last 7 days")}
  </div>
  <div class="fsec"><h4>Flavor profile</h4><div class="fchips">${groups}</div></div>
  <div class="fsec"><h4>Rating</h4>
    <div class="fchips">${RATING_STEPS.map((r) => chip(r ? `${icon("star", "xs")} ${r}+` : "Any", `data-f="rmin" data-v="${r}"`, f.rmin === r)).join("")}</div>
    <h4 style="margin-top:14px">Number of ratings</h4>
    <div class="fchips">${COUNT_STEPS.map((c) => chip(c ? `${c}+` : "Any", `data-f="rcmin" data-v="${c}"`, f.rcmin === c)).join("")}</div>
  </div>
  <div class="fsec"><h4>Strength</h4><div class="fchips">${STRENGTHS.map((s, i) => chip(esc(s) + n(sc.get(i + 1) || 0), `data-f="strength" data-v="${i + 1}"`, f.strength.has(i + 1))).join("")}</div></div>
  <div class="fsec"><h4>Pack size</h4><div class="fchips">${PACKS.map(([k, label]) => chip(esc(label) + n(pc.get(k) || 0), `data-f="packs" data-v="${k}"`, f.packs.has(k))).join("")}</div></div>
  <div class="fsec" id="f-brands"><h4>Brands ${f.brands.size ? `<button class="linkish" data-act="clear-brands">Clear</button>` : ""}</h4>
    <input class="brand-search" id="brand-q" type="search" placeholder="Find a brand…" value="${esc(brandQuery)}" autocomplete="off">
    <div class="brandlist">${brands || `<p class="hint">No brand matches.</p>`}</div>
  </div>
  <div class="fsec"><h4>Origin</h4><div class="fchips">${[["", "All"], ["ru", "Russian brands"], ["other", "Other brands"]].map(([v, l]) => chip(l, `data-f="origin" data-v="${v}"`, f.origin === v)).join("")}</div></div>
  <div class="fsec"><h4>HTReviews</h4><div class="fchips">${[["", "All"], ["rated", "Rated"], ["unrated", "Not on HTReviews"], ["review", "Needs a match check"]].map(([v, l]) => chip(l, `data-f="rated" data-v="${v}"`, f.rated === v)).join("")}</div></div>`;
}

export function quickbar(f, active) {
  const gc = counts(f, "groups", (p) => p.groups);
  const top = DATA.groups.filter((g) => gc.get(g.key) || f.groups.has(g.key));
  return [
    `<button type="button" class="chip primary" data-act="filters">${icon("sliders", "sm")} Filters${active ? ` <span class="n">${active}</span>` : ""}</button>`,
    chip("In stock", `data-f="stock"`, f.stock),
    chip(`${icon("star", "xs")} 4.5+`, `data-f="rmin" data-v="4.5"`, f.rmin === 4.5),
    chip("New", `data-f="isNew"`, f.isNew),
    chip("Back in stock", `data-f="isBack"`, f.isBack),
    chip(`Brands${f.brands.size ? ` <span class="n">${f.brands.size}</span>` : ""}`, `data-act="brands"`, f.brands.size > 0),
    ...top.map((g) => chip(esc(g.key), `data-f="groups" data-v="${esc(g.key)}"`, f.groups.has(g.key), `<span class="dot" style="--c:${g.color}"></span>`)),
  ].join("");
}

export function pills(f) {
  const out = [];
  const pill = (label, attrs) => `<button type="button" class="pill" ${attrs}>${label}${icon("x")}</button>`;
  if (f.q) out.push(pill(`“${esc(f.q)}”`, `data-clear="q"`));
  for (const b of f.brands) out.push(pill(esc(b.replace("\u0001", " · ") || b) + (b.endsWith("\u0001") ? "Main" : ""), `data-clear="brands" data-v="${esc(b)}"`));
  for (const g of f.groups) out.push(pill(esc(g), `data-clear="groups" data-v="${esc(g)}"`));
  for (const s of f.strength) out.push(pill(STRENGTHS[s - 1], `data-clear="strength" data-v="${s}"`));
  for (const k of f.packs) out.push(pill(PACKS.find((p) => p[0] === k)[1], `data-clear="packs" data-v="${k}"`));
  if (f.rmin) out.push(pill(`★ ${f.rmin}+`, `data-clear="rmin"`));
  if (f.rcmin) out.push(pill(`${f.rcmin}+ ratings`, `data-clear="rcmin"`));
  if (f.isNew) out.push(pill("New", `data-clear="isNew"`));
  if (f.isBack) out.push(pill("Back in stock", `data-clear="isBack"`));
  if (f.origin) out.push(pill(f.origin === "ru" ? "Russian brands" : "Other brands", `data-clear="origin"`));
  if (f.rated) out.push(pill({ rated: "Rated", unrated: "Not on HTReviews", review: "Needs a match check" }[f.rated], `data-clear="rated"`));
  if (out.length > 1) out.push(`<button type="button" class="pill clear" data-act="reset">Clear all</button>`);
  return out.join("");
}

// ── shopping list ──────────────────────────────────────────────────────
export function cartView() {
  const rows = cart.all().map((it) => ({ it, hit: DATA.bySku.get(it.id) }));
  if (!rows.length)
    return {
      title: "Shopping list",
      body: `<div class="empty"><h3>Your list is empty</h3><p>Open a flavor and tap <b>Add</b> on a size.<br>Then send the whole list to your World Hookah Market cart.</p></div>`,
    };
  let total = 0;
  const body = rows
    .map(({ it, hit }) => {
      if (!hit)
        return `<div class="cart-item"><div class="thumb"><span class="ph">?</span></div><div><div class="t">No longer listed</div><small>WHM product #${it.id}</small></div>
          <button class="btn sm ghost" data-act="qty" data-sku="${it.id}" data-q="0">${icon("x", "sm")}</button></div>`;
      const { p, s } = hit;
      total += s.p * it.qty;
      return `<div class="cart-item">
        ${thumb(p, 52)}
        <div><div class="t">${esc(p.n)}</div>
          <small>${esc(p.b)}${p.l ? ` · ${esc(p.l)}` : ""} · ${weight(s.g)} · ${money(s.p)}${s.st ? "" : ` · <span class="oos">sold out</span>`}</small>
          <small><a class="linkish" href="${cart.addUrl(s.id, it.qty)}" target="_blank" rel="noopener" data-act="sent" data-sku="${s.id}">${it.sent ? `${icon("check", "xs")} Sent — add again` : `Add to WHM cart ${icon("ext", "xs")}`}</a></small>
        </div>
        <div class="qty"><button data-act="qty" data-sku="${s.id}" data-q="${it.qty - 1}" aria-label="One less">${icon("minus", "sm")}</button><span>${it.qty}</span><button data-act="qty" data-sku="${s.id}" data-q="${it.qty + 1}" aria-label="One more">${icon("plus", "sm")}</button></div>
      </div>`;
    })
    .join("");
  return {
    title: `Shopping list · ${cart.count()}`,
    cls: "side",
    body: `${body}
      <div class="cart-sum"><span>Estimated total</span><b>${money(total)}</b></div>
      <p class="hint">Prices from World Hookah Market's catalog; shipping and tax are added at checkout.
      <b>Send all</b> opens one WHM window and adds each item in turn (about 3 seconds each), then shows your cart.
      If your browser blocks it, use the per-item links.</p>
      <p><button class="linkish" data-act="copy">${icon("copy", "xs")} Copy list as text</button> &nbsp; <button class="linkish" data-act="clear-cart" style="color:var(--bad)">Clear list</button></p>`,
    foot: `<a class="btn" href="${cart.cartUrl}" target="_blank" rel="noopener">Open WHM cart</a><button class="btn primary" data-act="send-all">${icon("cart", "sm")} Send all to WHM cart</button>`,
  };
}

// ── info / status ──────────────────────────────────────────────────────
export function infoView(st, token) {
  const s = DATA?.stats || st.stats || {};
  const rated = s.products ? Math.round((s.matched / Math.max(1, s.products - s.unmatchable)) * 100) : 0;
  return {
    title: "About this data",
    cls: "side",
    body: `
    <div class="d-block"><h3>Freshness</h3>
      <dl class="kv">
        <dt>Stock &amp; prices (World Hookah Market)</dt><dd>${ago(st.whm_at)}</dd>
        <dt>Ratings (HTReviews)</dt><dd>${ago(st.htr_at)}</dd>
      </dl>
      <p class="hint" style="margin-top:10px">Stock and prices refresh every two hours, ratings once a day, automatically.</p>
      ${st.running ? `<p><b>Refreshing…</b> ${esc(st.message)}</p>` : ""}
      ${st.error ? `<p class="hint" style="color:var(--bad)">Last refresh failed: ${esc(st.error)}</p>` : ""}
    </div>
    <div class="d-block"><h3>Catalog</h3>
      <dl class="kv">
        <dt>Flavors</dt><dd>${(s.products || 0).toLocaleString()}</dd>
        <dt>Sizes (WHM listings)</dt><dd>${(s.skus || 0).toLocaleString()}</dd>
        <dt>In stock</dt><dd>${(s.in_stock || 0).toLocaleString()}</dd>
        <dt>With an HTReviews match</dt><dd>${(s.matched || 0).toLocaleString()} (${rated}%)</dd>
        <dt>Brands not on HTReviews</dt><dd>${(s.unmatchable || 0).toLocaleString()} flavors</dd>
        <dt>Matches set by hand</dt><dd>${s.manual || 0}</dd>
      </dl>
      <p style="margin-top:12px"><button class="btn sm" data-act="review">${icon("wrench", "sm")} Review uncertain matches</button></p>
    </div>
    <div class="d-block"><h3>How “Best rated” works</h3>
      <p class="hint">A 5.0 from two people says less than a 4.7 from three hundred. <b>Best rated</b> blends each flavor's HTReviews
      average with the overall average, weighted by how many ratings it has, so well-loved flavors with lots of ratings come first.
      <b>Highest rating</b> sorts by the raw average instead.</p>
    </div>
    <div class="d-block"><h3>Refresh now</h3>
      ${st.admin_locked ? `<p class="hint">Refreshing and fixing matches need the admin token.</p><input class="field" id="admin-token" type="password" placeholder="Admin token" value="${esc(token)}" autocomplete="off"><div style="height:10px"></div>` : ""}
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn sm" data-act="refresh" data-kind="whm" ${st.running ? "disabled" : ""}>${icon("refresh", "sm")} Stock &amp; prices</button>
        <button class="btn sm" data-act="refresh" data-kind="all" ${st.running ? "disabled" : ""}>${icon("refresh", "sm")} Everything</button>
      </div>
      ${st.log?.length ? `<div class="logbox">${st.log.slice(-12).map(esc).join("<br>")}</div>` : ""}
    </div>
    <p class="hint" style="text-align:center;margin-top:16px">Data: <a href="https://worldhookahmarket.com" target="_blank" rel="noopener">World Hookah Market</a> ·
      <a href="https://htreviews.org" target="_blank" rel="noopener">HTReviews</a> · build ${esc(st.commit || "")}</p>`,
  };
}

// ── match fixer ────────────────────────────────────────────────────────
export function fixView(p, items, q = "") {
  const fq = q.trim().toLowerCase();
  const cur = p.h?.id;
  // Likely candidates first: the current match, then flavors sharing words
  // with the shop's name, then the rest alphabetically.
  const words = new Set(p.n.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => w.length > 2));
  const shared = (it) => it.n.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => words.has(w)).length;
  const ranked = items
    .map((it) => ({ it, k: it.id === cur ? 99 : shared(it) }))
    .sort((a, b) => b.k - a.k || a.it.n.localeCompare(b.it.n))
    .map((x) => x.it);
  const list = ranked
    .filter((it) => !fq || `${it.n} ${it.ru} ${it.line}`.toLowerCase().includes(fq))
    .slice(0, 150)
    .map(
      (it) => `<button class="fix-item${it.id === cur ? " cur" : ""}" data-act="pick" data-id="${it.id}">
        <span><b>${esc(it.n)}</b><small>${[it.ru, it.line].filter(Boolean).map(esc).join(" · ")}</small></span>
        <span class="hint">${it.r != null ? `★ ${it.r.toFixed(1)} · ${it.rc}` : "unrated"}</span></button>`,
    )
    .join("");
  return {
    title: "Fix rating match",
    body: `<p class="hint">Which HTReviews flavor is <b>${esc(p.b)} ${esc(p.n)}</b>${p.l ? ` (${esc(p.l)})` : ""}? Your choice sticks across refreshes.</p>
      <input class="field" id="fix-q" type="search" placeholder="Search ${esc(p.b)} on HTReviews…" value="${esc(q)}" autocomplete="off">
      <div class="fix-list">${list || `<p class="hint">Nothing matches “${esc(q)}”.</p>`}</div>`,
    foot: `${p.mo ? `<button class="btn" data-act="unpin">Back to automatic</button>` : ""}<button class="btn" data-act="pick" data-id="">Not on HTReviews</button>`,
  };
}
