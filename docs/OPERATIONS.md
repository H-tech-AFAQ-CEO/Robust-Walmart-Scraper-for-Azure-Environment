# Walmart Scraper – Setup, Operation, Recovery

**Author:** [Zulqarnain Ahmad](https://www.freelancer.com/u/zulqarnaina43)  
**In collaboration with team leader:** [Afaq Ahmad](https://www.freelancer.com/u/AFAQCEO) ([GitHub](https://github.com/H-tech-AFAQ-CEO))

---

## What it does
Per configured location, twice weekly: select store → verify store/pickup context → discover subcategories →
page through every listing → keep only Walmart-sold, pickup/in-store-available items → dedupe → validate →
publish `latest/<location>/products.json` **only if validation passes**.

## One-time setup
1. `config/locations.json`: set `id`, `zipcode`, `store_id` (the Walmart store number), optional `canaries`
   (usItemIds that should always be in that store's catalog – 10–20 recommended).
2. `config/categories.csv`: already contains the supplied 11 categories. Add a row to add a category;
   `Notes` text like `Exclude 'Farm Animals' subcategory` is parsed into exclusions.
3. **Calibrate against live Walmart (required once):**
   `pip install -r requirements.txt && playwright install chromium`
   `python -m walmart_scraper probe --location <id>`
   Check: `store_context.store_id` equals your store, `items_found` > 0, `sub_links_sample` contains real
   subcategories, and the printed `FIRST ITEM KEYS` include the fields the parser reads
   (`usItemId, name, canonicalUrl, image, priceInfo, sellerName, fulfillment*`). If not, adjust only
   `parser.py` (field paths) / `fetcher.select_store` (UI selectors). Everything else is payload-agnostic.
4. Azure: build/push image (`az acr build -t walmart-scraper:1.0.0 -r <acr> .`), then
   `az deployment group create -g <rg> -f infra/main.bicep -p image=<..> acrServer=<..> locationIds='["store_1"]'`.
   Schedule default `0 8 * * 1,4` (Mon/Thu 08:00 UTC). Proxy URL (if any) is passed as a secure parameter →
   Container Apps secret → `WS_PROXY_URL`; no secret lives in source.
   Storage uses a managed identity (Blob Data Contributor); there are no storage keys in the app.

## Settings (env vars, prefix `WS_`)
`PACE_MIN/PACE_MAX` (s between pages), `MAX_RETRIES`, `MAX_PAGES` (25), `MAX_DEPTH` (2), `MIN_YIELD_RATIO` (0.7),
`MIN_CANARY_RATIO`, `MIN_COMPLETENESS`, `ENRICH_UPC` (true), `INCLUDE_SPONSORED_ONLY` (false), `PROXY_URL`.

## Exit codes
0 published · 2 validation failed (not published) · 3 aborted (block/location mismatch; resumable) · 4 another run holds the lock.

## Data-integrity design
* **Never overwrite good data**: every run writes `runs/<job>/<run_id>/…`; `latest/<job>/…` is replaced only after
  `validate_run` passes. Report is written last as the commit marker.
* **Validation fails the run on**: store/fulfillment not positively verified or any mismatch; any category with 0
  records or < 70 % of last good run; any failed/blocked/incomplete node; canary products missing (< 60 %
  found); required-field completeness < 98 %; duplicates; non-empty gupc/unit_price; approximate weights; total < 70 % of prior.
* **Silent blocking**: HTTP 403/429/503, challenge markers, missing `__NEXT_DATA__`, exceptions → retried with
  exponential backoff + jitter; persistent failure marks the node `failed` (not "empty"); 3 consecutive failures
  abort the run (circuit breaker) with checkpoint kept. The scraper does not solve CAPTCHAs or evade challenges.
* **Location**: store id/ZIP/fulfillment read from every page payload and compared to config; mismatch aborts immediately.
* **Marketplace / shipping-only**: items with a non-Walmart seller, or without pickup/in-store fulfillment signal
  (or with no fulfillment signal at all), are rejected and counted (`rejected_marketplace`, `rejected_shipping_only`,
  `rejected_no_fulfillment_info`).
* **Sponsored / duplicates**: records keyed by usItemId. Sponsored placements never create records; a product
  seen only as sponsored is dropped (`sponsored_only_dropped`) unless `INCLUDE_SPONSORED_ONLY=true`. Leaf
  subcategories are scraped before parents so the most specific sub_category wins.
* **Resume**: `state/<job>/<run_id>/` stores node status, last completed page and all records (saved every 10 pages
  and at node end). A restarted job with an `in_progress` run < 36 h old continues it. `--fresh` forces a new run.

## Recovery
* Exit 3: just re-run (or let the retry / next schedule run). Check `runs/.../events.json` for why.
* Exit 2: read `runs/<job>/<run_id>/report.json → validation.problems`. `latest/` is still the previous good data.
* Stuck lock (blob lease expires after 60 s without renewal; local lock after 12 h): delete `locks/<job>.lock`.
* Walmart changed layout: re-run `probe`, adjust `parser.py`/`select_store`, run `pytest`.

## Adding locations / categories
Add an object to `locations.json` and its id to the Bicep `locationIds` parameter; add rows to `categories.csv`. No code change.

## Tests
`pip install -r requirements-dev.txt && pytest` – offline, uses synthetic fixtures only.
