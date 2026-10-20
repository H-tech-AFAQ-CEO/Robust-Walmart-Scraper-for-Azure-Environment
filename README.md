# Walmart Scraper (Production-Grade Azure & Playwright Pipeline)

**Author:** [Zulqarnain Ahmad](https://www.freelancer.com/u/zulqarnaina43)  
**In collaboration with team leader:** [Afaq Ahmad](https://www.freelancer.com/u/AFAQCEO) ([GitHub](https://github.com/H-tech-AFAQ-CEO))

## Repo

`https://github.com/H-tech-AFAQ-CEO/Robust-Walmart-Scraper-for-Azure-Environment.git`

Branch: `main` — two commits: `44ec542` (initial complete source), `2e4f70f` (availability fix + raw evidence + live-run plan + failed probe).

---

## Status (Oct 20, 2026)

**Code complete; live 500-product run not yet achieved.**

The full source code, configuration, Dockerfile, Azure Bicep infra, docs, tests, and unit-tested pipeline are committed. All 8 offline unit tests pass (synthetic fixtures only — clearly separated from live execution).

**Blocker:** A live probe against Walmart returns HTTP 200 but a bot-challenge page instead of `__NEXT_DATA__` (`reason: bot_challenge`, `items_found: 0`, `store_context` empty). Live execution on this datacenter IP is blocked until a residential/sticky proxy and `select_store` selector calibration are in place. No live records exist yet — do not treat the synthetic `output/` (6 test records) or offline `tests/` results as completed live execution.

See `LIVE_RUN_PLAN.md` for the concrete plan to reach the qualifying 500+ genuine live product run.

## Overview

A high-reliability, fault-tolerant Walmart product, pricing, and deals scraper built for Azure Container Apps (scheduled execution) and local operation. Designed to strict data-integrity standards: **never overwrite good data with incomplete or blocked runs**, enforce strict location/pickup verification, filter out third-party marketplace offers, preserve exact Walmart deal wording and PPM (Price Per Measure).

## Key Changes (Oct 20)

- **Availability rule fixed:** `parser.py::local_offer_check` no longer filters by stock status, shipping-only, or missing fulfillment. Unavailable/out-of-stock products are **retained** with their source-provided fulfillment context recorded. Only third-party marketplace offers are excluded (seller-based, never availability-based).
- **Raw response capture:** `WS_CAPTURE_RAW=1` persists raw HTML + `__NEXT_DATA__` + meta per request (even blocked pages) under `raw/<location>/<timestamp>/` as machine-readable evidence.
- **Fresh vs historical tracking:** `runner.py` tracks `records_fresh_this_run` vs `records_total_unique` so historical prices are never represented as newly verified.
- **Failed probe evidence captured:** `evidence/failed_probe_20261020.log` + raw challenge HTML in `raw/`.

## Key Features

- **Strict Data Integrity:** Atomic file writes and blob storage publishing via `publish_latest()` only after rigorous validation (`validate_run`).
- **Resumable Execution:** Durable checkpoints (`state/<job>/<run_id>/`) track nodes, pages, and records, enabling seamless continuation after interruption without re-fetching completed pages.
- **Store & Fulfillment Verification:** Validates store ID, ZIP code, and fulfillment context from every page payload; mismatch aborts the run.
- **Availability Retention:** Out-of-stock / shipping-only / no-fulfillment products are kept; availability never deletes a product.
- **Deal & PPM Extraction:** Separates volume deals (e.g. `2 for $5`, `BOGO`) from digital deals (`Clip Coupon`, `Save $X with Digital Coupon`) without price calculation. Captures display PPM only.
- **Anti-Blocking Safety:** Detects bot challenges (403/429/503, CAPTCHA markers, missing `__NEXT_DATA__`) with exponential backoff and circuit-breaker safety. No unsafe CAPTCHA bypassing.
- **Azure Ready:** Bicep templates for Azure Container Apps Jobs, Container Registry, and Managed Identity blob storage. Cron `0 8 * * 1,4` (twice weekly).

## Required JSON Field Order

`zipcode; store_name; store_location; store_logo; store_brand; category; sub_category; product_title; weight; regular_price; sale_price; volume_deals_description; volume_deals_price; digital_deals_description; digital_deals_price; image_url; url; upc; gupc; ppm; unit_price; crawl_date`

Missing values are empty strings (never `null`). `gupc` and `unit_price` are always `""` at the scraper stage. `ppm` is scraped as displayed, never calculated.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```
2. Configure location in `config/locations.json` and categories in `config/categories.csv` (already populated from `Walmart_Category_URLs.csv`).
3. Calibrate against live Walmart (required once):
   ```bash
   python -m walmart_scraper probe --location store_1
   ```
4. Run scraper:
   ```bash
   python -m walmart_scraper run --location store_1
   ```
5. Run tests:
   ```bash
   pytest
   ```

## Live Evidence

- `evidence/failed_probe_20261020.log` — exact failed probe (bot_challenge, 0 items, empty store context).
- `raw/store_1/20261020T054018/` — raw challenge HTML + meta (no `__NEXT_DATA__` present).
- `LIVE_RUN_PLAN.md` — concrete plan for the qualifying live 500-product run (residential proxy, selector calibration, full category traversal, repeat-run/resume/Azure verification).

See `docs/OPERATIONS.md`, `docs/WALKTHROUGH.md`, `ARCHITECTURE.md`, `CONTEST_ENTRY.md` for full details.
