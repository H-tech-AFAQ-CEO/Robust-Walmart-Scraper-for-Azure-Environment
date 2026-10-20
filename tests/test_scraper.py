"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Offline tests. All data below is SYNTHETIC test input, not Walmart data.
"""
from __future__ import annotations
import json, re
from pathlib import Path
import pytest

from walmart_scraper import runner, parser as P
from walmart_scraper.config import Category, Location, Settings
from walmart_scraper.deals import classify_deals
from walmart_scraper.fetcher import Page
from walmart_scraper.runner import Job
from walmart_scraper.schema import FIELDS
from walmart_scraper.storage import LocalStorage, LockHeld

LOC = Location(id="t1", zipcode="72712", store_id="100", canaries=["1"])


def item(i, **kw):
    d = {"usItemId": str(i), "name": f"Great Value Thing {i} 12 oz", "canonicalUrl": f"/ip/thing-{i}/{i}",
         "image": f"https://img/{i}.jpg", "sellerName": "Walmart.com", "brand": "Great Value",
         "fulfillmentBadgeGroups": [{"text": "Pickup today"}],
         "priceInfo": {"currentPrice": {"price": 2.5}, "unitPrice": {"priceString": "$0.21/oz"}}}
    d.update(kw)
    return d


# ---------------------------------------------------------------- unit
def test_deals():
    d = classify_deals(["2 for $5", "Clip Coupon: Save $2", "Walmart Cash $3"])
    assert d["volume_deals_description"] == "2 for $5" and d["volume_deals_price"] == "5.00"
    assert d["digital_deals_description"] == "Clip Coupon: Save $2" and d["digital_deals_price"] == ""
    d = classify_deals(["$3.99 each with Digital Coupon"])
    assert d["digital_deals_price"] == "3.99" and not d["volume_deals_description"]
    d = classify_deals(["Buy 1, Get 1 Free"])
    assert d["volume_deals_description"] and d["volume_deals_price"] == ""
    d = classify_deals(["Save $5 when you buy 5 with Digital Coupon"])
    assert d["digital_deals_description"] and not d["volume_deals_description"]
    assert classify_deals(["Cashback 5%", "Rebate"]) == classify_deals([])


def test_parse_rules():
    rec, why = P.parse_item(item(1), "Food", "Snacks", LOC, "2026-10-19")
    assert rec["regular_price"] == "2.50" and rec["sale_price"] == "" and rec["ppm"] == "$0.21/oz"
    assert rec["store_brand"] == "yes"
    rec, _ = P.parse_item(item(2, priceInfo={"currentPrice": {"price": 2.0}, "wasPrice": {"price": 3}}), "F", "", LOC, "d")
    assert (rec["regular_price"], rec["sale_price"], rec["ppm"]) == ("3.00", "2.00", "")
    assert P.parse_item(item(3, sellerName="SomeSeller"), "F", "", LOC, "d")[1] == "marketplace"
    # availability must never filter/delete: shipping-only and missing-fulfillment items are retained
    rec4, why4 = P.parse_item(item(4, fulfillmentBadgeGroups=[{"text": "Shipping, arrives tomorrow"}]), "F", "", LOC, "d")
    assert why4 == "" and rec4 is not None
    rec5, why5 = P.parse_item(item(5, fulfillmentBadgeGroups=None), "F", "", LOC, "d")
    assert why5 == "" and rec5 is not None
    assert P.parse_item(item(6, weight="approx. 2 lb"), "F", "", LOC, "d")[1] == "approx_weight"
    rec, _ = P.parse_item(item(7, brand="Acme", name="Acme Chips 8 oz"), "F", "", LOC, "d")
    assert rec["store_brand"] == "no"


# ---------------------------------------------------------------- fake site
class Fake:
    def __init__(self, site, store_id="100", zipc="72712", block_after=None):
        self.site, self.store_id, self.zipc, self.block_after = site, store_id, zipc, block_after
        self.calls = []

    def start(self): pass
    def close(self): pass
    def select_store(self): pass
    def screenshot(self, p): pass

    def fetch(self, url, want_links=False):
        self.calls.append(url)
        if self.block_after is not None and len(self.calls) > self.block_after:
            return Page(url=url, status=403, blocked=True, reason="http_403")
        m = re.match(r"([^?]+)(?:\?page=(\d+))?", url)
        base, pn = m.group(1), int(m.group(2) or 1)
        node = self.site[base]
        pages = node["pages"]
        items = pages[pn - 1] if pn <= len(pages) else []
        nd = {"props": {"pageProps": {"initialData": {"searchResult": {
            "itemStacks": [{"items": items}], "paginationV2": {"maxPage": len(pages)},
            "pageMetadata": {"location": {"storeId": self.store_id, "postalCode": self.zipc, "city": "Bentonville", "stateOrProvinceCode": "AR"}}}}}}}
        return Page(url=url, status=200, next_data=nd, sub_links=node.get("links", []))


def site():
    A, B = "https://www.walmart.com/cp/food/976759", "https://www.walmart.com/cp/pets/5440"
    S1 = "https://www.walmart.com/browse/food/snacks/976759_1001"
    return {
        A: {"pages": [[item(1)]], "links": [{"name": "Snacks", "url": S1 + "?x=1"},
                                           {"name": "Shop All Foods", "url": "https://www.walmart.com/cp/shop-all/976759_9"},
                                           {"name": "Recipes", "url": "https://www.walmart.com/cp/recipes/976759_8"}]},
        S1: {"pages": [[item(1), item(2), item(3, sellerName="Other"), item(9, isSponsoredFlag=True)],
                       [item(2), item(4, priceInfo={"currentPrice": {"price": 1}, "wasPrice": {"price": 2}}), item(5)]]},
        B: {"pages": [[item(20), item(21)]], "links": []},
    }


def mk(tmp_path, fk, **sk):
    s = Settings(state_dir=str(tmp_path / "state"), output_dir=str(tmp_path / "out"), pace_min=0, pace_max=0,
                 max_retries=1, enrich_upc=False, min_completeness=0.9, **sk)
    cats = [Category("Food", "https://www.walmart.com/cp/food/976759?povid=x", ["Farm Animals"]),
            Category("Pets", "https://www.walmart.com/cp/pets/5440")]
    return Job(LOC, cats, s, LocalStorage(s.output_dir), fk), s


@pytest.fixture(autouse=True)
def nosleep(monkeypatch):
    monkeypatch.setattr(runner, "backoff_sleep", lambda *a, **k: None)


def test_end_to_end_dedupe_and_publish(tmp_path):
    job, s = mk(tmp_path, Fake(site()))
    assert job.run() == 0
    out = json.loads((Path(s.output_dir) / "latest/t1/products.json").read_text())
    assert [list(r.keys()) for r in out][0] == FIELDS
    urls = [r["url"] for r in out]
    assert len(urls) == len(set(urls)) == 6       # 1,2,4,5 food + 20,21 pets; 3 marketplace; 9 sponsored-only dropped
    assert all(r["gupc"] == "" and r["unit_price"] == "" for r in out)
    rep = json.loads((Path(s.output_dir) / "latest/t1/report.json").read_text())
    assert rep["counters"]["duplicates_dropped"] >= 2 and rep["counters"]["rejected_marketplace"] == 1
    assert rep["counters"]["sponsored_only_dropped"] == 1 and rep["store_verified"]
    assert {r["sub_category"] for r in out if r["category"] == "Food"} == {"Snacks"}
    assert next(r for r in out if r["url"].endswith("/1"))["sub_category"] == "Snacks"  # leaf wins over parent


def test_store_mismatch_aborts_and_publishes_nothing(tmp_path):
    job, s = mk(tmp_path, Fake(site(), store_id="999"))
    assert job.run() == 3
    assert not (Path(s.output_dir) / "latest/t1/products.json").exists()


def test_blocked_run_never_replaces_good_data(tmp_path):
    job, s = mk(tmp_path, Fake(site()))
    assert job.run() == 0
    good = (Path(s.output_dir) / "latest/t1/products.json").read_text()
    job2, _ = mk(tmp_path, Fake(site(), block_after=0), max_consecutive_blocks=2)
    assert job2.run(fresh=True) == 3
    assert (Path(s.output_dir) / "latest/t1/products.json").read_text() == good


def test_thin_run_fails_validation_keeps_latest(tmp_path):
    job, s = mk(tmp_path, Fake(site()))
    assert job.run() == 0
    good = (Path(s.output_dir) / "latest/t1/products.json").read_text()
    thin = site()
    thin["https://www.walmart.com/cp/pets/5440"]["pages"] = [[]]       # silent empty category
    job2, _ = mk(tmp_path, Fake(thin))
    assert job2.run(fresh=True) == 2
    assert (Path(s.output_dir) / "latest/t1/products.json").read_text() == good
    rep = json.loads(sorted((Path(s.output_dir) / "runs/t1").glob("*/report.json"))[-1].read_text())
    assert any("Pets" in p for p in rep["validation"]["problems"])


def test_resume_continues_without_refetching(tmp_path):
    fk = Fake(site(), block_after=4)
    job, s = mk(tmp_path, fk, max_consecutive_blocks=1)
    assert job.run() == 3
    done_calls = list(fk.calls)
    fk2 = Fake(site())
    job2, _ = mk(tmp_path, fk2, max_consecutive_blocks=1)
    assert job2.run() == 0                       # resumed same run
    assert len(list(Path(s.state_dir, "t1").iterdir())) == 1
    ok_before = [u for u in done_calls[:4]]
    # discovery pages already fetched in run 1 are not fetched again
    assert fk2.calls.count("https://www.walmart.com/cp/food/976759?povid=x") == 0
    out = json.loads((Path(s.output_dir) / "latest/t1/products.json").read_text())
    assert len(out) == 6


def test_lock_prevents_overlap(tmp_path):
    job, s = mk(tmp_path, Fake(site()))
    h = job.st.acquire_lock("t1")
    assert job.run() == 4
    job.st.release_lock(h)
