# Minimum Prerequisites for a Genuine Future Live Run — Walmart #44 Milestone 1

This matrix separates requirements needed for **live collection** (relevant now) from requirements needed only for a **future Azure deployment** (out of scope for Milestone 1).

Classifications: Confirmed available / Missing / Unknown / Not required for Milestone 1.

| # | Requirement | Why it is needed | Already available? | Minimum action |
|---|-------------|------------------|--------------------|----------------|
| 1 | Source code + repository metadata | Basis for Milestone 1 and future live runs | Confirmed | None — present at `ede5bfe` / impl. at `2e4f70f` |
| 2 | Python 3.12 runtime | Execute the scraper | Confirmed | None — Python 3.12.10 installed |
| 3 | pytest >= 8 | Run offline validation tests | Confirmed | None — pytest 9.1.1 installed |
| 4 | Playwright 1.56.0 | Browser-based page fetching | Confirmed | None — Playwright 1.56.0 installed |
| 5 | Chromium browser | Render and fetch Walmart pages | Confirmed | None — chromium installed at `ms-playwright/chromium-1194` |
| 6 | Outbound network connectivity to walmart.com | Reach retailer endpoints | Unknown | Safe connectivity diagnostic only; do not bypass controls |
| 7 | Residential/sticky proxy (`WS_PROXY_URL`) | Walmart blocks datacenter IPs with bot challenge (confirmed in `evidence/failed_probe_20261020.log`) | Missing | Procure/configure a US residential/sticky proxy; inject as secret env var (never in source) |
| 8 | Store #44 entry in `config/locations.json` | Target the intended Walmart store #44 | Missing | Add store #44 (`id`, `zipcode`, `store_id`, `store_name`, `store_location`, optional `canaries`) |
| 9 | Canary product IDs (optional, recommended) | Silent-blocking / yield validation per `validate.py` | Missing | Optional — 10–20 `usItemId`s expected in store #44's catalog |
| 10 | Local disk space for `raw/`, `state/`, `output/` | Save responses, checkpoints, datasets | Confirmed | None |
| 11 | Execution time (~minutes per location) | Full category traversal and pagination | Confirmed | None |
| 12 | Azure subscription / Contributor rights | Container Apps Job deployment via `infra/main.bicep` | Not required for Milestone 1 | Defer to a separate Azure deployment milestone |
| 13 | Azure Managed Identity + Blob Storage | Production state/output persistence | Not required for Milestone 1 | Defer to a separate Azure deployment milestone |
| 14 | Azure cron schedule (`0 8 * * 1,4`) | Twice-weekly collection per store | Not required for Milestone 1 | Defer to a separate Azure deployment milestone |

## Notes

- Requirements 1–5 and 10–11 are confirmed available locally.
- Requirements 6–9 are missing or unknown and block live collection.
- Requirements 12–14 are Azure-specific and belong to a future milestone; they are not required to establish Milestone 1 or to run live collection locally.
- No retailer credentials, paid APIs, or new subscriptions are required by the code itself. The only external service hinted at is an optional residential proxy (`WS_PROXY_URL`), which is not a paid API mandated by the scraper.

## Evidence references

- Bot-challenge block on datacenter IP: `evidence/failed_probe_20261020.log`, `raw/store_1/20261020T054018/`
- Store #44 not configured: `config/locations.json` contains only `store_1` (store #100, Bentonville, AR)
- Proxy setting: `walmart_scraper/config.py` (`WS_PROXY_URL` → `Settings.proxy_url`), `infra/main.bicep` (`proxyUrl` secret parameter)
- Azure infra: `infra/main.bicep`
