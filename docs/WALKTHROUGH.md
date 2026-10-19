# Walkthrough & Demonstration Script

**Author:** [Zulqarnain Ahmad](https://www.freelancer.com/u/zulqarnaina43)  
**In collaboration with team leader:** [Afaq Ahmad](https://www.freelancer.com/u/AFAQCEO) ([GitHub](https://github.com/H-tech-AFAQ-CEO))

---

## Demo Flow

### 1. Installation & Environment Check
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
playwright install chromium
pytest
```
*Verification:* All tests pass successfully in < 2 seconds.

### 2. Probing Live Walmart
```bash
python -m walmart_scraper probe --location store_1
```
*Verification:* Displays bot detection classification, store context, and item schema keys.

### 3. Running the Scraper
```bash
python -m walmart_scraper run --location store_1
```
*Verification:* Acquires lock, discovers subcategories, pages through categories, verifies store context, runs validation, and publishes to `output/latest/store_1/products.json` and `report.json`.

### 4. Reliability & Recovery Testing
- Interruption recovery: Kill and resume.
- Overlap prevention: Second run exits with code 4 (`LockHeld`).
- Validation guard: Thin run fails validation and leaves `latest/` untouched.
