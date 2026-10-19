"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Required output schema. Field ORDER is part of the contract.
"""
from __future__ import annotations

FIELDS = [
    "zipcode", "store_name", "store_location", "store_logo", "store_brand",
    "category", "sub_category", "product_title", "weight", "regular_price",
    "sale_price", "volume_deals_description", "volume_deals_price",
    "digital_deals_description", "digital_deals_price", "image_url", "url",
    "upc", "gupc", "ppm", "unit_price", "crawl_date",
]


def finalize(rec: dict) -> dict:
    """Return record with exactly FIELDS in order, all values str ('' for missing).
    gupc and unit_price are ALWAYS forced to '' at the scraper stage."""
    out = {}
    for f in FIELDS:
        v = rec.get(f, "")
        out[f] = "" if v is None else str(v)
    out["gupc"] = ""
    out["unit_price"] = ""
    return out
