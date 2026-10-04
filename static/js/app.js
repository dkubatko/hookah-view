// App wiring: state, URL sync, rendering, sheets and actions.
import * as C from "./catalog.js";
import * as V from "./views.js";
import * as cart from "./cart.js";
import { $, $$, esc, debounce, toast, plural, money, weight, icon } from "./util.js";

const PAGE = 48;
const els = {
  q: $("#q"),
  qClear: $("#q-clear"),
  grid: $("#grid"),
  sentinel: $("#sentinel"),
  empty: $("#empty"),
  count: $("#count"),
  sort: $("#sort"),
  sortLabel: $("#sort-label"),
  sidebar: $("#sidebar"),
  quickbar: $("#quickbar"),
  sheet: $("#sheet"),
  scrim: $("#scrim"),
  cartCount: $("#cart-count"),
};

let f = location.search ? C.fromQuery(location.search) : C.loadPrefs(C.defaults());
let view = localStorage.getItem("hs_view") || "grid";
let results = [];
let shown = 0;
let brandQuery = "";
let showAllBrands = false;
// The brand list in the full filter panel is collapsed to a summary row.
let sidebarBrandsOpen = true;
let sheetBrandsOpen = false;
let section = "all"; // which part of the filters the filter sheet shows
let sheetKind = null; // "detail" | "filters" | "cart" | "info" | "fix"
let current = null; // product shown in the detail sheet
let fixState = null; // { items, q }
let status = {};

// ── rendering ──────────────────────────────────────────────────────────
function apply({ keepScroll = false } = {}) {
  C.DATA.reviewMode = f.rated === "review";
  C.DATA.stockOnly = f.stock;
  results = C.sort(C.filter(f), f.sort, f.q);
  shown = 0;
  els.grid.innerHTML = "";
  els.grid.className = `grid${view === "list" ? " list" : ""}`;
  more();
  const total = C.DATA.products.length;
  els.count.innerHTML = `<b>${results.length.toLocaleString()}</b> ${results.length === 1 ? "flavor" : "flavors"}${
    results.length !== total ? ` <span>of ${total.toLocaleString()}</span>` : ""
  }`;
  els.empty.hidden = results.length > 0;
  if (!results.length) {
    els.empty.innerHTML = `<h3>No flavors match</h3><p>Try fewer filters${f.stock ? " or include sold-out flavors" : ""}.</p>
      <button class="btn" data-act="reset">Clear filters</button>${f.stock ? ` <button class="btn" data-f="stock">Show sold out</button>` : ""}`;
  }
  renderFilters();
  syncUrl();
  if (!keepScroll) window.scrollTo({ top: 0 });
}

function more() {
  if (shown >= results.length) return;
  const next = results.slice(shown, shown + PAGE);
  els.grid.insertAdjacentHTML("beforeend", next.map(V.card).join(""));
  shown += next.length;
}

function renderFilters() {
  const active = C.activeCount(f);
  els.quickbar.innerHTML = V.quickbar(f, active, C.anyActive(f));
  // Re-rendering replaces the brand search box; keep focus and caret.
  const hadFocus = document.activeElement?.id === "brand-q";
  const caret = hadFocus ? document.activeElement.selectionStart : 0;
  if (getComputedStyle(els.sidebar).display !== "none") {
    const top = els.sidebar.scrollTop;
    els.sidebar.innerHTML = V.filters(f, { brandQuery, showAllBrands, brandsOpen: sidebarBrandsOpen, sidebar: true });
    els.sidebar.scrollTop = top;
  }
  if (sheetKind === "filters") {
    const body = $(".sheet-body", els.sheet);
    const top = body.scrollTop;
    body.innerHTML = V.filters(f, { section, brandQuery, showAllBrands, brandsOpen: sheetBrandsOpen });
    body.scrollTop = top;
    $("[data-act=show]", els.sheet).textContent = results.length ? `Show ${plural(results.length, "flavor")}` : "No matches";
  }
  if (hadFocus) {
    const input = $("#brand-q", sheetKind === "filters" ? els.sheet : els.sidebar);
    input?.focus();
    input?.setSelectionRange(caret, caret);
  }
  els.sort.value = f.sort;
  els.sortLabel.textContent = C.SORTS.find(([k]) => k === f.sort)[1];
  $$(".seg button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.view === view));
}

function syncUrl() {
  const qs = C.toQuery(f);
  const url = `${location.pathname}${qs ? "?" + qs : ""}${location.hash}`;
  if (url !== location.pathname + location.search + location.hash) history.replaceState(history.state, "", url);
  C.savePrefs(f);
}

function renderCartBadge() {
  const n = cart.count();
  els.cartCount.hidden = !n;
  els.cartCount.textContent = n;
}

// ── filter changes ─────────────────────────────────────────────────────
function toggleSet(set, v) {
  set.has(v) ? set.delete(v) : set.add(v);
}

function onFilter(el) {
  const k = el.dataset.f;
  const v = el.dataset.v;
  if (k === "brands") {
    // row: tick/untick the whole brand; all: whole brand instead of lines;
    // line: narrow a brand to particular lines.
    const brand = v.split("\u0001")[0];
    const dropLines = () => [...f.brands].forEach((x) => x.startsWith(brand + "\u0001") && f.brands.delete(x));
    const op = el.dataset.op || "row";
    if (op === "row") {
      const any = f.brands.has(brand) || [...f.brands].some((x) => x.startsWith(brand + "\u0001"));
      dropLines();
      if (any) f.brands.delete(brand);
      else f.brands.add(brand);
    } else if (op === "all") {
      dropLines();
      f.brands.add(brand);
    } else {
      f.brands.delete(brand);
      toggleSet(f.brands, v);
      if (![...f.brands].some((x) => x.startsWith(brand + "\u0001"))) f.brands.add(brand);
    }
  } else if (["groups", "packs"].includes(k)) toggleSet(f[k], v);
  else if (k === "strength") toggleSet(f.strength, +v);
  else if (["rmin", "rcmin"].includes(k)) f[k] = f[k] === +v ? 0 : +v;
  else if (["origin", "rated"].includes(k)) f[k] = f[k] === v ? "" : v;
  else if (["stock", "isNew", "isBack"].includes(k)) f[k] = el.type === "checkbox" ? el.checked : !f[k];
  apply();
}

function clearOne(k, v) {
  const d = C.defaults();
  if (f[k] instanceof Set) f[k].delete(k === "strength" ? +v : v);
  else f[k] = d[k];
  if (k === "q") els.q.value = "";
  apply();
}

// ── sheets ─────────────────────────────────────────────────────────────
function openSheet(kind, { title = "", body = "", foot = "", cls = "" }, { push = true } = {}) {
  const wasOpen = !!sheetKind;
  sheetKind = kind;
  els.sheet.className = `sheet ${cls}`;
  els.sheet.innerHTML = `<div class="sheet-grab"></div>
    <div class="sheet-head"><h2${title ? ' id="sheet-title"' : ""}>${title}</h2><button class="sheet-close" data-act="close" aria-label="Close">${icon("x")}</button></div>
    <div class="sheet-body">${body}</div>${foot ? `<div class="sheet-foot">${foot}</div>` : ""}`;
  els.sheet.hidden = false;
  els.scrim.hidden = false;
  els.sheet.classList.remove("closing");
  els.scrim.classList.remove("closing");
  document.body.classList.add("locked");
  // Back button / swipe-back closes the sheet instead of leaving the page.
  if (push && !wasOpen) history.pushState({ sheet: kind }, "", location.href.split("#")[0] + (kind === "detail" ? `#p=${encodeURIComponent(current.k)}` : ""));
  else if (kind === "detail") history.replaceState({ sheet: kind }, "", location.href.split("#")[0] + `#p=${encodeURIComponent(current.k)}`);
  // Focus the dialog itself (keyboard users can Tab on) without a ring on the X.
  setTimeout(() => els.sheet.focus({ preventScroll: true }), 50);
}

function updateSheet({ title, body, foot }) {
  const b = $(".sheet-body", els.sheet);
  const top = b.scrollTop;
  if (title !== undefined) $(".sheet-head h2", els.sheet).innerHTML = title;
  b.innerHTML = body;
  b.scrollTop = top;
  const ft = $(".sheet-foot", els.sheet);
  if (foot !== undefined && ft) ft.innerHTML = foot;
}

function closeSheet({ fromHistory = false } = {}) {
  if (!sheetKind) return;
  if (!fromHistory && history.state?.sheet) {
    history.back(); // popstate will call us again
    return;
  }
  sheetKind = null;
  current = null;
  fixState = null;
  els.sheet.classList.add("closing");
  els.scrim.classList.add("closing");
  document.body.classList.remove("locked");
  setTimeout(() => {
    if (sheetKind) return;
    els.sheet.hidden = true;
    els.scrim.hidden = true;
    els.sheet.innerHTML = "";
  }, 200);
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
}

window.addEventListener("popstate", () => {
  if (sheetKind && !history.state?.sheet) {
    closeSheet({ fromHistory: true });
    // Back restored the URL from before the sheet opened; filters changed
    // inside the sheet must be written back.
    syncUrl();
  }
  else if (!sheetKind && location.hash.startsWith("#p=")) openFromHash();
});

function openDetail(p, opts) {
  current = p;
  openSheet("detail", V.detail(p), opts);
}

function openFromHash() {
  const key = decodeURIComponent(location.hash.slice(3));
  const p = C.DATA.byKey.get(key);
  if (p) openDetail(p, { push: false });
}

function openFilters(sec = "all") {
  section = sec;
  sheetBrandsOpen = false;
  const clear = { all: "reset", brands: "clear-brands", rating: "clear-rating", flavor: "clear-groups" }[sec];
  openSheet("filters", {
    title: V.SECTION_TITLES[sec],
    cls: `filters-${sec}${sec === "brands" ? " full" : ""}`,
    body: V.filters(f, { section: sec, brandQuery, showAllBrands, brandsOpen: sheetBrandsOpen }),
    foot: `<button class="btn" data-act="${clear}">${sec === "all" ? "Reset all" : "Clear"}</button><button class="btn primary" data-act="show">Show ${plural(results.length, "flavor")}</button>`,
  });
}

const openCart = () => openSheet("cart", V.cartView());
const refreshCart = () => sheetKind === "cart" && updateSheet(V.cartView());

async function openInfo() {
  openSheet("info", V.infoView(status, adminToken()));
  await loadStatus();
  if (sheetKind === "info") updateSheet(V.infoView(status, adminToken()));
}

async function openFix() {
  const p = current;
  openSheet("fix", { title: "Fix rating match", body: `<p class="hint">Loading ${esc(p.b)} flavors from HTReviews…</p>` }, { push: false });
  current = p;
  const r = await fetch(`/api/htr/${encodeURIComponent(p.b)}`);
  const data = await r.json();
  fixState = { items: data.items, q: "" };
  updateSheet(V.fixView(p, fixState.items, ""));
  setTimeout(() => $("#fix-q")?.focus(), 50);
}

// drag-down to dismiss on touch screens
(function sheetDrag() {
  let y0 = null;
  let dy = 0;
  els.sheet.addEventListener("pointerdown", (e) => {
    if (!e.target.closest(".sheet-grab, .sheet-head") || e.target.closest("button") || matchMedia("(min-width:1080px)").matches) return;
    y0 = e.clientY;
    dy = 0;
    els.sheet.setPointerCapture(e.pointerId);
    els.sheet.style.transition = "none";
  });
  els.sheet.addEventListener("pointermove", (e) => {
    if (y0 == null) return;
    dy = Math.max(0, e.clientY - y0);
    els.sheet.style.translate = `0 ${dy}px`;
  });
  const end = () => {
    if (y0 == null) return;
    y0 = null;
    els.sheet.style.transition = "translate .2s";
    els.sheet.style.translate = "";
    if (dy > 90) closeSheet();
  };
  els.sheet.addEventListener("pointerup", end);
  els.sheet.addEventListener("pointercancel", end);
})();

// ── admin / server actions ─────────────────────────────────────────────
const adminToken = () => localStorage.getItem("hs_admin") || "";

async function api(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken() },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) throw new Error("Admin token required — set it under About this data.");
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function loadStatus() {
  try {
    status = await (await fetch("/api/status")).json();
  } catch {
    /* offline */
  }
  return status;
}

async function reloadCatalog() {
  await C.load({ fresh: true });
  apply({ keepScroll: true });
}

async function setMatch(htrId, unpin = false) {
  const p = current;
  try {
    await api(unpin ? "DELETE" : "PUT", "/api/match", unpin ? { key: p.k } : { key: p.k, htr_id: htrId });
    await reloadCatalog();
    const fresh = C.DATA.byKey.get(p.k);
    toast(unpin ? "Back to automatic matching" : htrId ? "Match saved" : "Marked as not on HTReviews");
    if (fresh) {
      current = fresh;
      sheetKind = "detail";
      els.sheet.className = "sheet detail";
      updateSheet({ title: "", ...V.detail(fresh), foot: undefined });
      $(".sheet-foot", els.sheet)?.remove();
    }
  } catch (e) {
    toast(e.message, 4000);
  }
}

let pollTimer;
async function startRefresh(kind) {
  try {
    const r = await api("POST", "/api/refresh", { kind });
    toast(r.started ? "Refresh started" : "A refresh is already running");
  } catch (e) {
    toast(e.message, 4000);
    return;
  }
  clearInterval(pollTimer);
  const before = status.built_at;
  pollTimer = setInterval(async () => {
    await loadStatus();
    if (sheetKind === "info") updateSheet(V.infoView(status, adminToken()));
    if (!status.running) {
      clearInterval(pollTimer);
      if (status.built_at !== before) {
        await reloadCatalog();
        toast("Catalog updated");
      }
    }
  }, 1500);
}

// ── events ─────────────────────────────────────────────────────────────
const onSearch = debounce(() => {
  f.q = els.q.value.trim();
  apply();
}, 120);
els.q.addEventListener("input", () => {
  els.qClear.hidden = !els.q.value;
  onSearch();
});
els.q.addEventListener("keydown", (e) => {
  if (e.key === "Enter") els.q.blur();
  if (e.key === "Escape") {
    els.q.value = "";
    els.qClear.hidden = true;
    onSearch();
  }
});
els.qClear.addEventListener("click", () => {
  els.q.value = "";
  els.qClear.hidden = true;
  f.q = "";
  apply();
  els.q.focus();
});

els.sort.innerHTML = C.SORTS.map(([k, l]) => `<option value="${k}">${l}</option>`).join("");
els.sort.addEventListener("change", () => {
  f.sort = els.sort.value;
  apply();
});
$$(".seg button").forEach((b) =>
  b.addEventListener("click", () => {
    view = b.dataset.view;
    localStorage.setItem("hs_view", view);
    apply({ keepScroll: true });
  }),
);

$("#btn-cart").addEventListener("click", openCart);
$("#btn-info").addEventListener("click", openInfo);
els.scrim.addEventListener("click", () => closeSheet());
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && sheetKind) closeSheet();
  if (e.key === "/" && !sheetKind && document.activeElement?.tagName !== "INPUT") {
    e.preventDefault();
    els.q.focus();
  }
});

// one delegated click handler for the whole app
document.addEventListener("click", async (e) => {
  const t = e.target;
  const fEl = t.closest("[data-f]");
  if (fEl && fEl.tagName !== "INPUT") return onFilter(fEl);
  const clr = t.closest("[data-clear]");
  if (clr) return clearOne(clr.dataset.clear, clr.dataset.v);
  const cardEl = t.closest(".card[data-k]");
  if (cardEl) return openDetail(C.DATA.byKey.get(cardEl.dataset.k));

  const a = t.closest("[data-act]");
  if (!a) return;
  const act = a.dataset.act;
  if (act === "close") closeSheet();
  else if (act === "reset") {
    const keepSort = f.sort;
    f = C.defaults();
    f.sort = keepSort;
    els.q.value = "";
    els.qClear.hidden = true;
    apply();
  } else if (act === "filters") openFilters("all");
  else if (act === "sec") openFilters(a.dataset.sec);
  else if (act === "toggle-brands") {
    if (a.closest("#sidebar")) sidebarBrandsOpen = !sidebarBrandsOpen;
    else sheetBrandsOpen = !sheetBrandsOpen;
    renderFilters();
  } else if (act === "all-brands") {
    showAllBrands = true;
    renderFilters();
  } else if (act === "clear-brands") {
    f.brands.clear();
    apply();
  } else if (act === "clear-rating") {
    f.rmin = 0;
    f.rcmin = 0;
    apply();
  } else if (act === "clear-groups") {
    f.groups.clear();
    apply();
  } else if (act === "show") closeSheet();
  else if (act === "add") {
    const sku = +a.dataset.sku;
    cart.add(sku);
    const hit = C.DATA.bySku.get(sku);
    toast(`Added ${hit.p.n} ${weight(hit.s.g)} to your list`);
    if (current) updateSheet(V.detail(current));
  } else if (act === "qty") {
    cart.setQty(+a.dataset.sku, +a.dataset.q);
  } else if (act === "sent") {
    cart.markSent(+a.dataset.sku);
  } else if (act === "send-all") {
    const list = cart.all().filter((i) => C.DATA.bySku.has(i.id));
    if (!list.length) return;
    a.disabled = true;
    const ok = await cart.sendAll(list, (n) => (a.textContent = `Adding ${n + 1} of ${list.length}…`));
    if (!ok) toast("Your browser blocked the window — use the per-item links instead", 5000);
    else toast("All items sent to your WHM cart");
    refreshCart();
  } else if (act === "copy") {
    const lines = cart.all().map((i) => {
      const hit = C.DATA.bySku.get(i.id);
      return hit ? `${i.qty} × ${hit.p.b} ${hit.p.n} ${weight(hit.s.g)} — ${money(hit.s.p)} — ${hit.s.u}` : `${i.qty} × WHM #${i.id}`;
    });
    await navigator.clipboard?.writeText(lines.join("\n"));
    toast("List copied");
  } else if (act === "clear-cart") {
    if (confirm("Remove everything from your list?")) cart.clear();
  } else if (act === "fix") openFix();
  else if (act === "pick") setMatch(a.dataset.id ? +a.dataset.id : null);
  else if (act === "unpin") setMatch(null, true);
  else if (act === "refresh") {
    const tok = $("#admin-token");
    if (tok) localStorage.setItem("hs_admin", tok.value.trim());
    startRefresh(a.dataset.kind);
  } else if (act === "review") {
    closeSheet();
    f = C.defaults();
    f.stock = false;
    f.rated = "review";
    apply();
  }
});

document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches("input[type=checkbox][data-f]")) onFilter(t);
  if (t.id === "admin-token") localStorage.setItem("hs_admin", t.value.trim());
});

document.addEventListener("input", (e) => {
  if (e.target.id === "brand-q") {
    brandQuery = e.target.value;
    renderFilters();
  } else if (e.target.id === "fix-q" && fixState) {
    fixState.q = e.target.value;
    const list = V.fixView(current, fixState.items, fixState.q);
    const tmp = document.createElement("div");
    tmp.innerHTML = list.body;
    $(".fix-list", els.sheet).replaceWith($(".fix-list", tmp));
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const t = e.target;
  if (t.matches(".card[data-k]")) {
    e.preventDefault();
    openDetail(C.DATA.byKey.get(t.dataset.k));
  } else if (t.matches(".brow[data-f]")) {
    e.preventDefault();
    onFilter(t);
  }
});

// iOS keeps fixed elements pinned to the layout viewport, so with the
// keyboard up a bottom sheet ends up behind it.  Track the visual viewport
// and fit the open sheet into the space above the keyboard.
if (window.visualViewport) {
  const vv = window.visualViewport;
  const sync = () => {
    const kb = window.innerHeight - vv.height > 120 && !matchMedia("(min-width:1080px)").matches;
    document.documentElement.style.setProperty("--vvh", `${vv.height}px`);
    document.documentElement.style.setProperty("--vvt", `${vv.offsetTop}px`);
    els.sheet.classList.toggle("kb", kb && !!sheetKind);
    if (kb && document.activeElement?.matches(".sheet input")) {
      document.activeElement.scrollIntoView({ block: "nearest" });
    }
  };
  vv.addEventListener("resize", sync);
  vv.addEventListener("scroll", sync);
}

new IntersectionObserver((entries) => entries.some((x) => x.isIntersecting) && more(), { rootMargin: "1200px" }).observe(els.sentinel);

cart.onChange(() => {
  renderCartBadge();
  refreshCart();
  if (sheetKind === "detail" && current) updateSheet(V.detail(current));
});

// ── boot ───────────────────────────────────────────────────────────────
async function boot() {
  els.q.value = f.q;
  els.qClear.hidden = !f.q;
  els.grid.innerHTML = V.skeleton();
  renderCartBadge();
  let data = null;
  try {
    data = await C.load();
  } catch (e) {
    els.grid.innerHTML = "";
    els.empty.hidden = false;
    els.empty.innerHTML = `<h3>Couldn't load the catalog</h3><p>${esc(e.message)}</p><button class="btn" onclick="location.reload()">Retry</button>`;
    return;
  }
  if (!data) {
    // First run: the server is still fetching both sites.
    els.count.textContent = "Fetching catalog for the first time…";
    setTimeout(boot, 4000);
    return;
  }
  apply({ keepScroll: true });
  if (location.hash.startsWith("#p=")) openFromHash();
  loadStatus();
}
boot();
