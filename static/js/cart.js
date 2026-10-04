// Shopping list, kept in localStorage and handed to WHM's WooCommerce cart.
//
// WooCommerce adds a product with GET /?add-to-cart=<id>&quantity=<n>, using
// the shopper's own WHM session cookie, so the hand-off has to happen in the
// shopper's browser: one link per item, or "send all", which walks a single
// popup window through the add-to-cart URLs and finishes on the WHM cart.

const KEY = "hs_cart_v1";
const WHM = "https://worldhookahmarket.com";
const listeners = new Set();

let items = read();

function read() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v.filter((i) => i && i.id && i.qty > 0) : [];
  } catch {
    return [];
  }
}

function write() {
  localStorage.setItem(KEY, JSON.stringify(items));
  listeners.forEach((fn) => fn(items));
}

// Another tab changed the list.
window.addEventListener("storage", (e) => {
  if (e.key === KEY) {
    items = read();
    listeners.forEach((fn) => fn(items));
  }
});

export const onChange = (fn) => listeners.add(fn);
export const all = () => items;
export const count = () => items.reduce((n, i) => n + i.qty, 0);
export const qtyOf = (id) => items.find((i) => i.id === id)?.qty || 0;

export function add(id, qty = 1) {
  const it = items.find((i) => i.id === id);
  if (it) it.qty = Math.min(99, it.qty + qty);
  else items.push({ id, qty, sent: false });
  write();
}

export function setQty(id, qty) {
  items = qty > 0 ? items.map((i) => (i.id === id ? { ...i, qty: Math.min(99, qty), sent: false } : i)) : items.filter((i) => i.id !== id);
  write();
}

export function markSent(id) {
  items = items.map((i) => (i.id === id ? { ...i, sent: true } : i));
  write();
}

export function clear() {
  items = [];
  write();
}

export const addUrl = (id, qty) => `${WHM}/cart/?add-to-cart=${id}&quantity=${qty}`;
export const cartUrl = `${WHM}/cart/`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Walk one popup through every add-to-cart URL. Must be called from a click. */
export async function sendAll(list, onStep) {
  const w = window.open("", "whm-cart");
  if (!w) return false;
  try {
    w.document.title = "Adding to cart…";
    w.document.body.innerHTML =
      '<p style="font:16px system-ui;padding:24px;color:#444">Adding your list to the World Hookah Market cart…</p>';
  } catch {
    /* window already shows WHM from an earlier run */
  }
  for (const [n, it] of list.entries()) {
    onStep?.(n, it);
    w.location.replace(`${WHM}/?add-to-cart=${it.id}&quantity=${it.qty}`);
    // The add happens server-side as soon as WHM receives the request; give
    // it time to land before the next navigation cancels the page load.
    await sleep(2600);
    markSent(it.id);
  }
  w.location.replace(cartUrl);
  w.focus?.();
  return true;
}
