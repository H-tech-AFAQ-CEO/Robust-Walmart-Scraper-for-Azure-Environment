# Next Steps — Walmart #44 Milestone 1

## Part 1: Prioritized actions to unblock genuine live Walmart collection

These are the concrete, ordered actions needed before any live 500-product demonstration can occur.

1. **Add Walmart store #44 to `config/locations.json`.**
   - The repository currently configures only `store_1` (store #100, ZIP 72712, Bentonville, AR). There is no store #44 entry.
   - Required fields: `id` (e.g. `store_44`), `zipcode`, `store_id` (Walmart store number for #44), `store_name`, `store_location`, optional `canaries` (10–20 `usItemId`s).
   - File: `config/locations.json`
   - Owner: client (store identifiers must be confirmed by the client; do not guess).

2. **Obtain and configure a residential/sticky proxy (`WS_PROXY_URL`).**
   - Walmart blocks datacenter IPs with a bot challenge (`evidence/failed_probe_20261020.log`: `reason: bot_challenge`, status 200, no `__NEXT_DATA__`, 0 items).
   - The scraper already supports `WS_PROXY_URL` via `Settings.proxy_url` (`walmart_scraper/config.py`) and `infra/main.bicep` (`proxyUrl` secret parameter). No code change needed — only configuration.
   - The proxy must be a US residential/sticky IP; it is injected as a secret and never stored in source code.
   - Owner: client (secure credential channel; do not publish in repository).

3. **Re-run the probe and calibrate `select_store`.**
   - Command: `python -m walmart_scraper probe --location store_44` (after step 1).
   - Goal: `__NEXT_DATA__` present, `store_context.store_id` matches #44, `zipcode` matches, `items_found > 0`, `sub_links_sample` contains real subcategories.
   - If the store UI flow times out (as it did for `store_1`), calibrate `fetcher.py::select_store()` selectors against live Walmart. Adjust only `parser.py` field paths / `select_store()` selectors — the pipeline is payload-agnostic.
   - Owner: engineer.

4. **Run the full live scrape.**
   - Command: `python -m walmart_scraper run --location store_44 --fresh` with `WS_CAPTURE_RAW=1` and `WS_PROXY_URL` set.
   - Process all 11 categories from `config/categories.csv` and all applicable subcategories (depth up to 2), paginate to `max_pages` (25), retain unavailable products, dedupe by `usItemId`/canonical URL, enrich UPC from PDP.
   - Target: >= 500 unique genuine products across multiple categories/subcategories.
   - Owner: engineer.

## Part 2: Separate future milestones (NOT part of Milestone 1)

The following must be tracked as distinct milestones and are **not** claimed complete:

### Milestone 2 — 500-product live demonstration
- Deliver `output/latest/store_44/products.json` with 500+ genuine products, 22 fields in required order, empty strings for missing values, blank `gupc`/`unit_price`, scraped PPM, approximate-weight exclusions, bulk/family-pack/multipack preservation, volume vs. digital deal separation.
- Supporting evidence: `report.json` (totals, runtime, by-category counts, duplicate count, field completeness, deal/PPM stats, store verification), `raw/` per-request HTML + `__NEXT_DATA__`, reproducible collection logs.

### Milestone 3 — Full uncapped production traversal
- Complete traversal of every category and applicable subcategory without sampling caps or `max_pages` artificial limits beyond Walmart's own pagination.
- Category-level product counts reported; zero-product or thin categories flagged.

### Milestone 4 — Observed interruption/recovery
- Kill a live run mid-execution, then resume without `--fresh`; confirm checkpoint resumes from the last completed page/node without re-fetching.
- Confirm `latest/` is not replaced by an incomplete run.

### Milestone 5 — Azure execution/deployment acceptance
- Deploy via `infra/main.bicep` to Azure Container Apps Job with twice-weekly cron (`0 8 * * 1,4`).
- Managed Identity blob storage, `WS_PROXY_URL` as secret, blob-lease lock, AzureFile state share.
- Observed fresh run, store verification, random record checks, category-coverage review, duplicate/missing-field checks.

## What must NOT be done (per Milestone 1 scope)

- Do not represent offline `tests/` results as live execution.
- Do not fabricate a 500-product dataset.
- Do not claim store #44 is verified (it is not configured, and no response-bound evidence exists).
- Do not claim Azure acceptance (not deployed).
- Do not bypass the bot challenge or retailer access controls.

## Single highest-priority next action

**Add Walmart store #44 to `config/locations.json` and configure a residential/sticky proxy (`WS_PROXY_URL`), then re-run `python -m walmart_scraper probe --location store_44` until `__NEXT_DATA__` is present and `store_context.store_id` matches #44.** Without store #44 configuration and live access past the bot challenge, no live collection can proceed.
