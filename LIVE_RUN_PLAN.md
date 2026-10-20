# Live 500-Product Run Plan — Walmart Scraper (Updated Oct 20)

## 1. Exact failed-probe evidence (raw)

**Command:** `python -m walmart_scraper probe --location store_1`  
**Env:** `WS_CAPTURE_RAW=1`, headless Chromium (Playwright), local machine, datacenter IP.

**evidence/failed_probe_20261020.log (machine-readable JSON log):**
```json
{"ts":"2026-10-19 22:40:00,626","lvl":"WARNING","log":"ws.fetch","msg":"store UI flow incomplete (TimeoutError); relying on cookie + verification"}
{
  "blocked": true,
  "reason": "bot_challenge",
  "status": 200,
  "store_context": {"store_id":"","zipcode":"","fulfillment":"","city":"","state":""},
  "items_found": 0,
  "max_page": null,
  "sub_links_sample": []
}
```

**Raw response evidence captured** (`raw/store_1/20261020T054018/`):
- `https___www.walmart.com_cp_food_9767...html` — full challenge-page HTML (17,669 bytes)
- `https___www.walmart.com_cp_food_9767...next_data.json` — absent (no `__NEXT_DATA__` present)
- `https___www.walmart.com_cp_food_9767...meta.json` — `{"url": "...cp/food/976759...", "status": 200, "blocked": true, "reason": "bot_challenge", "latency": 0.0}`

**Root cause:** Walmart returns HTTP 200 but serves a bot-challenge page instead of the catalog; `__NEXT_DATA__` is absent, `store_context` is empty, and `items_found = 0`. The `select_store` UI flow (`Pickup or delivery` → ZIP → store selector) timed out. This is a perimeter-defense (bot-detection) block on a datacenter IP, not a scraper logic bug. Store UI selectors are also uncalibrated against live Walmart.

## 2. Code changes already made (committed locally, pending push)

- `parser.py::local_offer_check`: removed ALL availability/stock/fulfillment filtering (`out_of_stock`, `no_fulfillment_info`, `shipping_only` rejections). Only third-party marketplace offers are excluded (seller-based, not availability-based). Unavailable/out-of-stock/shipping-only products are now RETAINED with their source-provided fulfillment context recorded.
- `fetcher.py`: added `capture_raw` (env `WS_CAPTURE_RAW=1`) to persist raw HTML + `__NEXT_DATA__` + meta per request as machine-readable evidence. Saved even for blocked responses.
- `runner.py`: `records_fresh_this_run` counter tracks newly observed records vs. checkpoint-carried historical records; `records_total_unique` in report.
- `tests/test_scraper.py`: updated `test_parse_rules` so shipping-only / missing-fulfillment items assert retention (`why == ""`), matching the new availability rule.
- `config.py`: added `capture_raw` setting.

## 3. Concrete plan for the qualifying live 500-product run

### Phase A — Unblock live access (required before any live run)
1. Obtain residential/sticky proxy (rotating residential IPs, US-based). Configure via `WS_PROXY_URL` (secret, never in source). Datacenter IPs are consistently challenged.
2. Calibrate `fetcher.select_store` UI selectors against live Walmart using `python -m walmart_scraper probe --location store_1` until `store_context.store_id == "100"` and `zipcode == "72712"` and `items_found > 0`. Adjust only `parser.py` field paths / `select_store` selectors; the pipeline is payload-agnostic.
3. Verify `__NEXT_DATA__` contains `searchResult.itemStacks` with real items, `storeId`/`postalCode`, and fulfillment signals.

### Phase B — Full live scrape (no sampling caps)
1. Run `python -m walmart_scraper run --location store_1 --fresh` with `WS_CAPTURE_RAW=1` and `WS_PROXY_URL` set.
2. Process every category in `Walmart_Category_URLs.csv` (11 categories) and ALL applicable subcategories via `discover_children` (depth up to 2), excluding CSV-listed subcategories ('Shop All Foods', 'Recipes', 'Farm Animals').
3. Paginate every listing to `max_pages` (25 cap) using `paginationV2.maxPage`; no featured/sponsored/sale-only limiting; lazy-load scroll included.
4. Retain unavailable products (out-of-stock, shipping-only, no pickup) — availability never filters.
5. Dedupe by `usItemId`/canonical URL across categories and pagination overlap.
6. Enrich UPC from PDP when available (`ENRICH_UPC=true`).
7. Target: >= 500 unique genuine products across multiple categories/subcategories.

### Phase C — Verification evidence
- Store/fulfillment context from **actual source responses** (`store_context.store_id`, `zipcode`, `fulfillment` parsed from `__NEXT_DATA__` on every page), not cookies or output labels.
- Raw HTML + `__NEXT_DATA__` saved per request (`raw/`) for auditor re-verification.
- `crawl_date` set to collection date, final field.
- `gupc` and `unit_price` forced `""`; PPM scraped as displayed (never calculated).
- Approx-weight products excluded ("approx", "approximately", etc.).
- Volume vs. digital deals split preserving exact wording; no price calculation.
- Bulk/family-size/multipack products included with actual source identities/sizes.

### Phase D — Reliability tests (separate from live dataset)
1. **Repeat-run:** Second consecutive run; confirm `latest/` only replaced when validation passes; report counts stable.
2. **Interruption/resume:** Kill mid-run, re-run without `--fresh`; confirm checkpoint resumes from last completed page/node without re-fetching.
3. **Availability change example:** Document one product transitioning available→unavailable across runs while keeping the same `usItemId`/identity; report resulting count changes (record retained, stock flag changes in source context).
4. **Fresh vs historical:** Report `records_fresh_this_run` vs. `records_total_unique`; historical prices never represented as newly verified.
5. **Azure deployment:** Container Apps Job, cron `0 8 * * 1,4` (twice weekly, Mon/Thu 08:00 UTC), managed identity, `WS_PROXY_URL` as secret, `runs/` + `latest/` on Blob, lock via blob lease, resume via AzureFile state share (`infra/main.bicep`).

### Phase E — Delivery artifacts
- `output/latest/store_1/products.json` — live 500+ records, 22 fields in required order.
- `output/latest/store_1/report.json` — totals, runtime, by-category/by-sub-category counts, duplicate count, field completeness, deal/PPM stats, store verification, fresh vs historical counts.
- `evidence/failed_probe_20261020.log` + `raw/` — exact failed-probe raw evidence.
- `raw/` per-request HTML + `__NEXT_DATA__` from the qualifying run.
- Machine-readable structured JSON logs (stdout, `lvl`/`log`/`msg`).
- Source commit hash + `git log`.
- `tests/` offline suite (synthetic only, clearly separated from live).
- `docs/OPERATIONS.md`, `docs/WALKTHROUGH.md`, `ARCHITECTURE.md`, `CONTEST_ENTRY.md`.

## 4. Availability rule — expected count impact
Previously out-of-stock / shipping-only / no-fulfillment items were dropped (counters `rejected_out_of_stock`, `rejected_shipping_only`, `rejected_no_fulfillment_info`). Under the new rule they are retained:
- **No products deleted for availability.** Count only decreases for: approximate-weight wording, no price, no item ID, or third-party marketplace.
- If a previously-scraped product goes out of stock on a repeat run, the same `usItemId` is retained; its `weight`/`regular_price`/`sale_price`/fulfillment context reflect the fresh source observation; `crawl_date` updates.
- Count changes between runs will be reported in `report.json` (`by_category`, `records_fresh_this_run`, counters) with a note identifying any available→unavailable identity-retained product.

## 5. Realistic delivery date
Given the live-access blocker (residential proxy procurement + selector calibration against a dynamic bot-challenge target) is outside code control:
- **Code/config fixes + offline validation:** complete (this commit).
- **Qualifying live 500-product run + evidence:** estimated **3–5 business days** after residential proxy + live selector calibration are in place. Cannot commit to an earlier date because the failed probe proves live execution is currently blocked and cannot be fabricated.

## 6. Separation statement
Offline `tests/` results (synthetic fixtures, 8/8 passing) are unit checks only and are **not** represented as live execution. All live results will carry `crawl_date`, `records_fresh_this_run`, and `raw/` source evidence so they are auditable and distinct from simulated data.
