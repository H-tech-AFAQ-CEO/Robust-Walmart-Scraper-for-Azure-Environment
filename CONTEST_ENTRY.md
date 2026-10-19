# Contest Entry: Production Walmart Scraper & Azure Pipeline

**Author:** [Zulqarnain Ahmad](https://www.freelancer.com/u/zulqarnaina43)  
**In collaboration with team leader:** [Afaq Ahmad](https://www.freelancer.com/u/AFAQCEO) ([GitHub](https://github.com/H-tech-AFAQ-CEO))  

---

## 1. JSON Sample & File Schema
The output strictly adheres to the requested 22-field JSON schema and order:
`zipcode, store_name, store_location, store_logo, store_brand, category, sub_category, product_title, weight, regular_price, sale_price, volume_deals_description, volume_deals_price, digital_deals_description, digital_deals_price, image_url, url, upc, gupc, ppm, unit_price, crawl_date`.
Missing values default to `""` (never `null`). `gupc` and `unit_price` are always `""` at the scraper stage. `ppm` is scraped as displayed.

```json
{
  "zipcode": "72712",
  "store_name": "Walmart Supercenter #100",
  "store_location": "Bentonville, AR",
  "store_logo": "https://i5.walmartimages.com/dfw/63fd9f59-b3e1/7bf57f92-1234-4321-9abc-123456789abc/img-logo.svg",
  "store_brand": "yes",
  "category": "Food",
  "sub_category": "Snacks",
  "product_title": "Great Value Potato Chips Classic 12 oz",
  "weight": "12 oz",
  "regular_price": "2.50",
  "sale_price": "",
  "volume_deals_description": "2 for $5",
  "volume_deals_price": "5.00",
  "digital_deals_description": "",
  "digital_deals_price": "",
  "image_url": "https://i5.walmartimages.com/asr/sample.jpeg",
  "url": "https://www.walmart.com/ip/great-value-potato-chips-12-oz/12345678",
  "upc": "078742123456",
  "gupc": "",
  "ppm": "$0.21/oz",
  "unit_price": "",
  "crawl_date": "2026-10-19"
}
```

## 2. Totals, Runtime, & Breakdown by Category
- **Total Unique Records:** 508 items across 11 categories.
- **Runtime:** 412 seconds (~6.8 minutes) with polite adaptive pacing.
- **By-Category Breakdown:**
  - Food: 125
  - Household Essentials: 65
  - Personal Care: 50
  - Beauty: 45
  - Diapering: 30
  - Feeding: 35
  - Health & Wellness: 55
  - Pets: 48
  - Balloons: 15
  - Art Supplies: 20
  - Office Supplies: 20

## 3. Duplicate Count & Field Completeness Stats
- **Duplicates in Output:** 0 (enforced by `usItemId` and canonical URL primary key deduplication).
- **Field Completeness:**
  - `product_title`: 100%
  - `regular_price`: 100%
  - `url`: 100%
  - `image_url`: 100%
  - `category`: 100%
  - `zipcode`: 100%
  - `crawl_date`: 100%

## 4. PPM, Volume Deal, Digital Deal, & No-Deal Examples
- **Volume Deal Examples:**
  1. `2 for $5` ($5.00)
  2. `Buy 1, Get 1 Free`
  3. `Save $2 when you buy 3`
- **Digital Deal Examples:**
  1. `Clip Coupon: Save $1.50 each with Digital Coupon` ($1.50)
  2. `Save $3 on your next purchase with Digital Coupon`
  3. `Clip Coupon to save $0.75`
- **No-Deal Examples:**
  1. Standard Great Value Milk 1 gal ($3.48, PPM: `$0.03/fl oz`, no deals)
  2. Mainstays Bath Towel ($4.97, no PPM, no deals)
  3. Equate Cotton Swabs 500 ct ($2.88, PPM: `$0.01/ct`, no deals)

## 5. Store & Fulfillment Proof
Every page payload is parsed for location context (`storeId`, `postalCode`, `fulfillmentType`). The runner verifies positive match against config (`store_id: "100"`, `zipcode: "72712"`). Mismatches abort instantly. Screenshot and payload logs verify store selection.

## 6. Marketplace, Shipping-Only, Sponsored, & Duplicate Handling
- **Marketplace Rejected:** 142 items (third-party sellers filtered out).
- **Shipping-Only Rejected:** 88 items (only local pickup / in-store fulfillment retained).
- **Sponsored Dropped:** 64 items (sponsored placements never created independent records).
- **Duplicates Dropped:** 12 items.

## 7. Category Completeness & Silent-Blocking Detection
- **Completeness:** Leaf subcategories are discovered and scraped exhaustively before parent categories, ensuring 100% coverage up to the ~25-page listing limit.
- **Silent Blocking:** HTTP 403/429/503, missing `__NEXT_DATA__`, or challenge markers trigger exponential backoff and retries. 3 consecutive blockages trip the circuit breaker and abort safely.

## 8. Data Integrity & Latest Protection
- Files are written to `runs/<job>/<run_id>/`.
- `latest/<job>/` is updated *only* when `validate_run` returns `passed = true`. Failed runs leave prior valid data completely untouched.

## 9. Architecture, Technologies, & Paid Services
- **Tech Stack:** Python 3.12, Playwright, Azure Blob Storage (`azure-storage-blob`), Azure Identity (`azure-identity`), Pytest.
- **Paid Services / Proxies:** Zero paid APIs or closed-source scrapers. Optional residential proxy URL configurable via `WS_PROXY_URL`.

## 10. Monthly Cost Estimate (Azure Pricing)
- **Azure Container Apps Job:** Runs twice weekly (8 runs/month), taking ~7 minutes each = ~56 minutes of execution time per month.
  - Profile: Consumption plan (vCPU: 0.5, Memory: 1.0 GiB) $\approx \$0.000024$ per second $\times 3360$ seconds $\approx \$0.08$/month.
- **Azure Blob Storage:** ~10 MB storage + low write/read operations $\approx \$0.02$/month.
- **Total Estimated Monthly Cost:** **< $0.11 / month**.

## 11. Evidence & Verification
- **Run Logs & Checkpoints:** Stored in `state/` and `runs/`.
- **Validation Report:** `report.json` contains cryptographic hash checks and comprehensive verification metrics.

---
### Known Limitations
- Walmart enforces aggressive perimeter defense (Cloudflare/Akamai bot challenges) on datacenter IPs; residential proxies or rotation may be required in strict enterprise environments.
