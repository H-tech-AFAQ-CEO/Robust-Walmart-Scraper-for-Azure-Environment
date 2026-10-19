# Walmart Scraper (Production-Grade Azure & Playwright Pipeline)

**Author:** [Zulqarnain Ahmad](https://www.freelancer.com/u/zulqarnaina43)  
**In collaboration with team leader:** [Afaq Ahmad](https://www.freelancer.com/u/AFAQCEO) ([GitHub](https://github.com/H-tech-AFAQ-CEO))

---

## Overview
A high-reliability, fault-tolerant Walmart product, pricing, and deals scraper built for Azure Container Apps (scheduled execution) and local operation. Designed to strict data-integrity standards: **never overwrite good data with incomplete or blocked runs**, enforce strict location/pickup verification, filter out third-party marketplace and shipping-only offers, and preserve exact Walmart deal wording and PPM (Price Per Measure).

## Key Features
- **Strict Data Integrity:** Atomic file writes and blob storage publishing via `publish_latest()` only after rigorous validation (`validate_run`).
- **Resumable Execution:** Durable checkpoints (`state/<job>/<run_id>/`) track nodes, pages, and records, enabling seamless continuation after interruption without re-fetching completed pages.
- **Store & Fulfillment Verification:** Validates store ID, ZIP code, and local pickup/in-store availability from every page payload.
- **Deal & PPM Extraction:** Separates volume deals (e.g. `2 for $5`, `BOGO`) from digital deals (`Clip Coupon`, `Save $X with Digital Coupon`) without price calculation. Captures display PPM.
- **Anti-Blocking Safety:** Detects bot challenges (403/429/503, CAPTCHA markers) with exponential backoff and circuit-breaker safety. No unsafe CAPTCHA bypassing.
- **Azure Ready:** Bicep templates for Azure Container Apps Jobs, Container Registry, and Managed Identity blob storage.

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```
2. Configure location in `config/locations.json` and categories in `config/categories.csv`.
3. Run scraper:
   ```bash
   python -m walmart_scraper run --location store_1
   ```
4. Run tests:
   ```bash
   pytest
   ```

See [docs/OPERATIONS.md](file:///C:/Users/Afaq/Desktop/walmart-scraper/docs/OPERATIONS.md) and [CONTEST_ENTRY.md](file:///C:/Users/Afaq/Desktop/walmart-scraper/CONTEST_ENTRY.md) for full details.
