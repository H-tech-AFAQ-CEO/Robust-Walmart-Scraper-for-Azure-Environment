"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Pure functions: Walmart page payload (__NEXT_DATA__) -> records. No network.
"""
from __future__ import annotations
import re
from typing import Any, Iterator

from .deals import classify_deals

PRIVATE_LABEL = {
    "great value", "equate", "parent's choice", "parents choice", "mainstays", "marketside",
    "bettergoods", "better goods", "sam's choice", "ol' roy", "special kitty", "pen+gear",
    "pen + gear", "time and tru", "wag", "freshness guaranteed", "our finest", "hyper tough",
    "onn", "clear american", "o ya!", "purely", "no boundaries", "walmart", "everstart",
    "better homes & gardens", "spring valley", "faded glory", "athletic works", "fresh express?",
}
PRIVATE_LABEL.discard("fresh express?")
APPROX_RE = re.compile(r"\b(approx\.?|approximately|est\.|estimated|avg\.|average weight)|~", re.I)
WALMART_SELLERS = {"walmart.com", "walmart", "walmart inc.", ""}


def deep_find(obj: Any, key: str) -> Iterator[Any]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from deep_find(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from deep_find(v, key)


def first(obj: Any, *keys: str) -> Any:
    for k in keys:
        for v in deep_find(obj, k):
            if v not in (None, "", [], {}):
                return v
    return None


def extract_items(nd: dict) -> list[dict]:
    items: list[dict] = []
    stacks = None
    try:
        stacks = nd["props"]["pageProps"]["initialData"]["searchResult"]["itemStacks"]
    except (KeyError, TypeError):
        pass
    if stacks is None:
        stacks = list(deep_find(nd, "itemStacks"))
        stacks = stacks[0] if stacks else []
    for st in stacks or []:
        for it in (st or {}).get("items", []) or []:
            if isinstance(it, dict) and (it.get("usItemId") or it.get("canonicalUrl")):
                items.append(it)
    return items


def max_page(nd: dict) -> int | None:
    v = first(nd, "maxPage")
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def total_results(nd: dict) -> int | None:
    v = first(nd, "totalCount", "aggregatedCount")
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def extract_store_context(nd: dict) -> dict:
    loc = first(nd, "location") if isinstance(first(nd, "location"), dict) else {}
    sid = first(nd, "storeId", "assortmentStoreId", "pickupStoreId") or (loc or {}).get("storeId")
    zipc = first(nd, "postalCode", "zipCode") or (loc or {}).get("postalCode")
    ful = first(nd, "fulfillmentType", "fulfillmentMethod", "selectedFulfillment")
    return {
        "store_id": str(sid) if sid else "",
        "zipcode": str(zipc)[:5] if zipc else "",
        "fulfillment": str(ful) if ful else "",
        "city": str((loc or {}).get("city", "")),
        "state": str((loc or {}).get("stateOrProvinceCode", "")),
    }


def _money(v: Any) -> str:
    if v in (None, ""):
        return ""
    if isinstance(v, dict):
        v = v.get("price", v.get("priceString", ""))
    s = str(v).replace(",", "").replace("$", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    return f"{float(m.group()):.2f}" if m else ""


def _item_id(it: dict) -> str:
    if it.get("usItemId"):
        return str(it["usItemId"])
    m = re.search(r"/ip/(?:[^/]+/)?(\d+)", it.get("canonicalUrl", "") or "")
    return m.group(1) if m else ""


def local_offer_check(it: dict) -> tuple[bool, str]:
    """Keep every product regardless of stock status or pickup/delivery/purchase availability.
    Availability must never filter or delete products. Only third-party marketplace offers
    are excluded (they are not Walmart prices). Fulfillment context is still read from the
    source payload and recorded, never used to drop a record."""
    seller = str(it.get("sellerName") or "").strip().lower()
    if seller not in WALMART_SELLERS:
        return False, "marketplace"
    if it.get("isMarketplace") or it.get("marketplaceItem"):
        return False, "marketplace"
    return True, ""


def _collect_promo_texts(it: dict) -> list[str]:
    out: list[str] = []

    def walk(o: Any, hit: bool):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, hit or any(w in k.lower() for w in
                                   ("badge", "flag", "promo", "offer", "deal", "saving", "coupon", "multibuy")))
        elif isinstance(o, list):
            for v in o:
                walk(v, hit)
        elif isinstance(o, str) and hit and 3 < len(o) < 300 and not o.startswith("http"):
            out.append(o.strip())
    walk(it, False)
    return list(dict.fromkeys(out))


def parse_item(it: dict, category: str, sub_category: str, loc, crawl_date: str,
               store_ctx: dict | None = None) -> tuple[dict | None, str]:
    """Return (record, '') or (None, reject_reason)."""
    ok, why = local_offer_check(it)
    if not ok:
        return None, why
    pi = it.get("priceInfo") or {}
    cur = _money(pi.get("currentPrice") or it.get("price"))
    was = _money(pi.get("wasPrice"))
    if not cur:
        return None, "no_price"
    if was and float(was) > float(cur):
        regular, sale = was, cur
    else:
        regular, sale = cur, ""
    title = str(it.get("name") or "").strip()
    weight = str(it.get("weight") or it.get("productSizeDisplay") or it.get("size") or "").strip()
    if not weight:
        m = re.search(r"(\d+(?:\.\d+)?\s*(?:fl\.?\s*oz|oz|lb|lbs|g|kg|ml|l|ct|count|pack|qt|gal)\b\.?)", title, re.I)
        weight = m.group(1) if m else ""
    if APPROX_RE.search(weight) or APPROX_RE.search(title):
        return None, "approx_weight"
    up = pi.get("unitPrice")
    ppm = ""
    if isinstance(up, dict):
        ppm = str(up.get("priceString") or up.get("price") or "").strip()
    elif up:
        ppm = str(up).strip()
    if ppm and not re.search(r"/|per\s", ppm, re.I):
        ppm = ""  # not a per-measure display; never reconstruct
    deals = classify_deals(_collect_promo_texts(it))
    brand = str(it.get("brand") or "").strip().lower()
    is_pl = brand in PRIVATE_LABEL or any(title.lower().startswith(p + " ") for p in PRIVATE_LABEL)
    url = it.get("canonicalUrl") or ""
    if url.startswith("/"):
        url = "https://www.walmart.com" + url
    rec = {
        "zipcode": loc.zipcode, "store_name": loc.store_name, "store_location": loc.store_location,
        "store_logo": loc.store_logo, "store_brand": "yes" if is_pl else "no",
        "category": category, "sub_category": sub_category, "product_title": title, "weight": weight,
        "regular_price": regular, "sale_price": sale, **deals,
        "image_url": it.get("image") or (it.get("imageInfo") or {}).get("thumbnailUrl") or "",
        "url": url, "upc": str(it.get("upc") or ""), "ppm": ppm, "crawl_date": crawl_date,
    }
    rec["_id"] = _item_id(it)
    return rec, ""


def extract_upc_from_pdp(nd: dict) -> str:
    v = first(nd, "upc")
    return re.sub(r"\D", "", str(v)) if v else ""
