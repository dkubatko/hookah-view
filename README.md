# Hookah Shop

Shop [World Hookah Market](https://worldhookahmarket.com) tobacco with ratings from
[HTReviews](https://htreviews.org). A rewrite of the original `hookah-view` app.

## Run it

```bash
uv sync
echo "MODERNMT_API_KEY=…" > .env      # only needed to translate new Russian flavor names
uv run python -m app.main            # http://localhost:8440
uv run pytest -q
```

On first start with an empty `data/` the app fetches both sites (about 30 s) and
then refreshes by itself: WHM stock and prices every 2 h, HTR ratings every 24 h.
To reuse the old app's paid translations: `uv run python -m app.translate <old>/data/.translations.json`.

| env | default | |
|---|---|---|
| `PORT` | 8440 | |
| `DATA_DIR` | `./data` | JSON files: raw data, catalog, overrides, caches |
| `WHM_REFRESH_MINUTES` | 120 | stock/prices |
| `HTR_REFRESH_HOURS` | 24 | ratings |
| `ADMIN_TOKEN` | unset | if set, refresh and match fixes need it (`X-Admin-Token`) |
| `MODERNMT_API_KEY` | unset | Russian → English for HTR names |

## How it works

```
WHM Store API ─(category 91 only, ~35 req, 5 s)──┐
                                                 ├─ build ─ catalog.json ─ /api/catalog (gzip+ETag) ─ browser
HTR /postData objectByBrand (~120 req, 20 s) ────┘    ↑                                        filters/sorts locally
           └─ ModernMT for Russian-only names (cached) overrides.json (hand-fixed matches)
```

**Sources.** WHM is WooCommerce; everything sellable sits under the *Hookah Tobacco*
category, paged by id and checked against `X-WP-Total` so a partial fetch never
replaces good data. HTR has no public API, but its own brand pages load flavors
from `POST /postData {"action": "objectByBrand"}`, which already includes English and
Russian names, rating, rating count, strength, status, flavor tags and an image.
(The old app fetched ~1,500 product pages to find English names.)

**Catalog** (`app/parse.py`, `app/rules.py`). Brand and line come from WHM's category
tree; the flavor name is what's left of the product name after brand, line, weight and
catalog-number noise. `rules.py` only lists exceptions. Sizes of one flavor become one
product, including listings WHM files under different categories.

**Matching** (`app/match.py`). One match per flavor, not per size. Each HTR flavor gets
candidate strings (Latin names, `ex.` names, ModernMT translations and alternatives,
transliteration, URL slug). The score requires word coverage in both directions, so
"Orange Mint" no longer matches plain "Orange" (the old app accepted those). Same-line
candidates get a bonus. Weaker matches (< 84) show as "≈ match" and can be reviewed under
*About this data → Review uncertain matches*. Fixes made in the UI are stored in
`overrides.json` and survive refreshes.

**Ratings.** *Best rated* uses a Bayesian average: `(prior·15 + rating·n) / (15 + n)`,
so a 5.0 from two people doesn't outrank a 4.7 from three hundred.

**Frontend** (`static/`). No build step: ES modules, one CSS file. The whole catalog
(~230 KB gzipped) loads once; search, filters and facet counts run in the browser.
Filters live in the URL; sheets hook into history so Back closes them on phones.
The shopping list is in localStorage and hands items to WHM's own cart with
`?add-to-cart=<id>&quantity=<n>`.

## Deploy

Pushing to `main` runs the tests and publishes `ghcr.io/dkubatko/hookah-view:latest`
(`.github/workflows/docker.yml`). On Tower the stack in `deploy/compose.yaml` runs that
image behind Nginx Proxy Manager (shop.3rdplacelounge.com), and Watchtower picks up new
images automatically (its own Watchtower, scoped to this stack). `/api/health` reports
the running commit.

## Layout

```
app/  config  store  text  vocab  translate  rules  parse  match  build  refresh  main
      sources/whm.py  sources/htr.py
static/  index.html  styles.css  js/{app,catalog,views,cart,util}.js
tests/
```
