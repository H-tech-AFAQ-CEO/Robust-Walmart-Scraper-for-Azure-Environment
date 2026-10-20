"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Orchestration: lock -> resume -> verify store -> discover -> scrape -> enrich -> validate -> publish.
"""
from __future__ import annotations
import json, logging, random, time
from collections import Counter
from pathlib import Path

from . import parser as P
from .categories import discover_children
from .checkpoint import Checkpoint
from .fetcher import backoff_sleep
from .schema import finalize
from .storage import LockHeld, publish_latest
from .validate import validate_run

log = logging.getLogger("ws.run")


class Abort(Exception):
    """Circuit breaker / location mismatch: stop, keep checkpoint, exit non-zero."""


def _base(url: str) -> str:
    return url.split("?")[0].rstrip("/")


def _is_sponsored(it: dict) -> bool:
    return bool(it.get("isSponsoredFlag") or it.get("isSponsored") or it.get("sponsoredProduct")
                or (it.get("adsInfo") or it.get("adId")))


class Job:
    def __init__(self, loc, cats, settings, storage, fetcher, sleep=time.sleep):
        self.loc, self.cats, self.s, self.st, self.f, self.sleep = loc, cats, settings, storage, fetcher, sleep
        self.cp: Checkpoint | None = None
        self.consec_blocks = 0
        self.store_verified = False
        self.t_start = time.time()

    # ---------------------------------------------------------------- fetch w/ retry
    def get(self, url: str, want_links=False):
        for attempt in range(self.s.max_retries + 1):
            if hasattr(self.st, "renew_lock") and getattr(self, "lock", None):
                self.st.renew_lock(self.lock)   # 60s Azure lease, renewed every request
            pg = self.f.fetch(url, want_links=want_links) if want_links else self.f.fetch(url)
            self.cp.counters["requests"] += 1
            self.cp.counters["latency_ms_total"] += int(pg.latency * 1000)
            if not pg.blocked:
                self.consec_blocks = 0
                self._check_store(pg)
                self.sleep(random.uniform(self.s.pace_min, self.s.pace_max))
                return pg
            self.cp.counters["retries"] += 1
            self.cp.event("blocked", url=url, reason=pg.reason, attempt=attempt)
            log.warning("blocked/failed %s reason=%s attempt=%d", url, pg.reason, attempt)
            if attempt < self.s.max_retries:
                backoff_sleep(attempt)
        self.consec_blocks += 1
        self.cp.counters["blocked_pages"] += 1
        if self.consec_blocks >= self.s.max_consecutive_blocks:
            raise Abort(f"{self.consec_blocks} consecutive blocked pages; stopping to avoid hammering")
        return None

    def _check_store(self, pg):
        ctx = P.extract_store_context(pg.next_data or {})
        bad = None
        if ctx["store_id"] and ctx["store_id"] != str(self.loc.store_id):
            bad = f"store_id {ctx['store_id']} != {self.loc.store_id}"
        elif ctx["zipcode"] and not ctx["store_id"] and ctx["zipcode"] != self.loc.zipcode[:5]:
            bad = f"zip {ctx['zipcode']} != {self.loc.zipcode}"
        elif ctx["fulfillment"] and any(w in ctx["fulfillment"].lower() for w in ("delivery", "shipping")) \
                and "pickup" not in ctx["fulfillment"].lower() and "store" not in ctx["fulfillment"].lower():
            bad = f"fulfillment context {ctx['fulfillment']}"
        if bad:
            self.cp.counters["store_mismatch"] += 1
            self.cp.event("store_mismatch", detail=bad, url=pg.url)
            raise Abort(f"LOCATION MISMATCH: {bad}")
        if ctx["store_id"] == str(self.loc.store_id) or (not ctx["store_id"] and ctx["zipcode"] == self.loc.zipcode[:5] and ctx["zipcode"]):
            self.store_verified = True
        if not self.loc.store_location and ctx["city"]:
            self.loc.store_location = f"{ctx['city']}, {ctx['state']}".strip(", ")
        if not self.cp.meta.get("store_ctx"):
            self.cp.meta["store_ctx"] = ctx

    # ---------------------------------------------------------------- phases
    def discover(self):
        for cat in self.cats:
            key = _base(cat.url)
            node = self.cp.nodes.setdefault(key, {"category": cat.name, "sub": "", "url": key, "depth": 0,
                                                    "status": "pending", "last_page": 0, "kept": 0,
                                                    "discovered": False, "excluded": cat.excluded_subcategories})
            if node["discovered"]:
                continue
            pg = self.get(cat.url, want_links=True)
            if pg is None:
                node["status"] = "failed"; node["fail_reason"] = "discovery blocked"; continue
            if not self.loc.store_logo and pg.logo:
                self.loc.store_logo = pg.logo
            kids = discover_children(cat.url, pg.sub_links, cat.excluded_subcategories)
            self.cp.event("discovered", category=cat.name, subs=len(kids))
            for k in kids:
                kk = _base(k["url"])
                self.cp.nodes.setdefault(kk, {"category": cat.name, "sub": k["name"], "url": kk, "depth": 1,
                                              "status": "pending", "last_page": 0, "kept": 0, "discovered": False,
                                              "excluded": cat.excluded_subcategories})
            node["discovered"] = True
            self.cp.save()
        if self.s.max_depth >= 2:
            for key, node in list(self.cp.nodes.items()):
                if node["depth"] != 1 or node["discovered"] or node["status"] == "failed":
                    continue
                pg = self.get(key, want_links=True)
                if pg is None:
                    node["discovered"] = True   # leaf-scrape will still cover it
                    continue
                for k in discover_children(key, pg.sub_links, node["excluded"]):
                    kk = _base(k["url"])
                    if kk in self.cp.nodes:
                        continue
                    self.cp.nodes[kk] = {"category": node["category"], "sub": node["sub"], "url": kk, "depth": 2,
                                         "status": "pending", "last_page": 0, "kept": 0, "discovered": True,
                                         "excluded": node["excluded"]}
                node["discovered"] = True
                self.cp.save()

    def scrape_nodes(self):
        order = sorted(self.cp.nodes.values(), key=lambda n: -n["depth"])   # leaves first, parents last
        for i, node in enumerate(order):
            if node["status"] == "done":
                continue
            node["status"] = "running"
            log.info("[%d/%d] %s > %s (depth %d) from page %d", i + 1, len(order), node["category"],
                     node["sub"] or "-", node["depth"], node["last_page"] + 1)
            self.scrape_node(node)
            self.cp.save()

    def scrape_node(self, node):
        cp = self.cp
        page_no = node["last_page"] + 1
        while page_no <= self.s.max_pages:
            pg = self.get(f"{node['url']}?page={page_no}")
            if pg is None:
                node["status"] = "failed"; node["fail_reason"] = f"blocked at page {page_no}"
                return
            items = P.extract_items(pg.next_data or {})
            mp = P.max_page(pg.next_data or {})
            if not items:
                if page_no == 1:
                    cp.event("empty_first_page", url=node["url"])
                    cp.counters["empty_first_pages"] += 1
                node["status"] = "done"
                return
            for it in items:
                self.take(it, node)
            node["last_page"] = page_no
            if page_no % 10 == 0:
                cp.save()
            if mp is not None and page_no >= mp:
                break
            page_no += 1
        node["status"] = "done"

    def take(self, it, node):
        cp = self.cp
        cp.counters["items_seen"] += 1
        iid = P._item_id(it)
        if not iid:
            cp.counters["rejected_no_id"] += 1
            return
        if _is_sponsored(it):
            cp.counters["sponsored_seen"] += 1
            if iid not in cp.records and iid not in cp.sponsored_only:
                cp.sponsored_only[iid] = {"item": it, "category": node["category"], "sub": node["sub"]}
            return
        if iid in cp.records:
            cp.counters["duplicates_dropped"] += 1
            return
        rec, why = P.parse_item(it, node["category"], node["sub"], self.loc, cp.meta["crawl_date"])
        if rec is None:
            cp.counters[f"rejected_{why}"] += 1
            return
        cp.records[iid] = rec
        cp.counters["records_fresh_this_run"] += 1
        node["kept"] += 1
        cp.sponsored_only.pop(iid, None)

    def resolve_sponsored(self):
        if not self.s.include_sponsored_only:
            cp = self.cp
            cp.counters["sponsored_only_dropped"] = len([i for i in cp.sponsored_only if i not in cp.records])
            return
        for iid, v in self.cp.sponsored_only.items():
            if iid not in self.cp.records:
                rec, why = P.parse_item(v["item"], v["category"], v["sub"], self.loc, self.cp.meta["crawl_date"])
                if rec:
                    self.cp.records[iid] = rec

    def enrich_upc(self):
        if not self.s.enrich_upc:
            return
        misses = 0
        todo = [i for i, r in self.cp.records.items() if not r["upc"] and not r.get("_upc_tried")]
        log.info("UPC enrichment for %d products", len(todo))
        for n, iid in enumerate(todo, 1):
            rec = self.cp.records[iid]
            try:
                pg = self.get(rec["url"])
            except Abort:
                log.warning("UPC enrichment stopped (blocking); upc is 'when available'")
                self.cp.event("upc_enrichment_stopped")
                break
            rec["_upc_tried"] = True
            if pg is None:
                misses += 1
                if misses >= 10:
                    break
                continue
            rec["upc"] = P.extract_upc_from_pdp(pg.next_data or {})
            if n % 25 == 0:
                self.cp.save()

    # ---------------------------------------------------------------- finish
    def finish(self, prior_report):
        cp = self.cp
        self.resolve_sponsored()
        order = {c.name: i for i, c in enumerate(self.cats)}
        recs = sorted(cp.records.values(), key=lambda r: (order.get(r["category"], 99), r["sub_category"]))
        out = [finalize(r) for r in recs]
        v = validate_run(out, cp, prior_report, [c.name for c in self.cats], self.loc.canaries,
                         self.s, self.store_verified)
        active = cp.meta.get("active_seconds", 0) + (time.time() - self.t_start)
        deals = Counter()
        for r in out:
            deals["with_ppm"] += bool(r["ppm"])
            deals["with_volume_deal"] += bool(r["volume_deals_description"])
            deals["with_digital_deal"] += bool(r["digital_deals_description"])
            deals["with_sale_price"] += bool(r["sale_price"])
            deals["with_upc"] += bool(r["upc"])
            deals["store_brand_yes"] += r["store_brand"] == "yes"
        report = {
            "run_id": cp.meta["run_id"], "job": self.loc.id, "crawl_date": cp.meta["crawl_date"],
            "store_expected": {"store_id": self.loc.store_id, "zipcode": self.loc.zipcode},
            "store_observed": cp.meta.get("store_ctx"), "store_verified": self.store_verified,
            "runtime_seconds": round(active), "total": len(out),
            "by_category": dict(Counter(r["category"] for r in out)),
            "by_sub_category": dict(Counter(f"{r['category']} > {r['sub_category']}" for r in out)),
            "records_fresh_this_run": cp.counters.get("records_fresh_this_run", 0),
            "records_total_unique": len(out),
            "counters": dict(cp.counters), "deal_stats": dict(deals),
            "nodes": {"total": len(cp.nodes), "failed": [k for k, n in cp.nodes.items() if n["status"] == "failed"]},
            "validation": v,
        }
        return out, report

    def run(self, fresh=False) -> int:
        job = self.loc.id
        try:
            lock = self.st.acquire_lock(job)
        except LockHeld:
            log.error("another run holds the lock for %s; exiting", job)
            return 4
        self.lock = lock
        code = 1
        try:
            self.cp, resumed = Checkpoint.open_or_create(Path(self.s.state_dir), job, self.s.resume_max_hours, fresh)
            log.info("run %s (%s) store=%s zip=%s", self.cp.meta["run_id"], "RESUMED" if resumed else "new",
                     self.loc.store_id, self.loc.zipcode)
            prior = self.st.read_text(f"latest/{job}/report.json")
            prior = json.loads(prior) if prior else None
            self.f.start()
            try:
                self.f.select_store()
                self.discover()
                self.scrape_nodes()
                self.enrich_upc()
            except Abort as a:
                log.error("ABORT: %s", a)
                self.cp.event("abort", reason=str(a))
                self.cp.meta["status"] = "in_progress"      # resumable
                self.cp.save()
                return 3
            finally:
                self.f.close()
            out, report = self.finish(prior)
            rid = self.cp.meta["run_id"]
            self.st.write_text(f"runs/{job}/{rid}/products.json", json.dumps(out, indent=2, ensure_ascii=False))
            self.st.write_text(f"runs/{job}/{rid}/report.json", json.dumps(report, indent=2))
            self.st.write_text(f"runs/{job}/{rid}/events.json", json.dumps(self.cp.events))
            if report["validation"]["passed"]:
                publish_latest(self.st, job, rid, json.dumps(out, indent=2, ensure_ascii=False), report)
                self.cp.meta["status"] = "completed"
                log.info("PUBLISHED %d records", len(out))
                code = 0
            else:
                self.cp.meta["status"] = "failed_validation"
                log.error("VALIDATION FAILED - latest/ untouched: %s", report["validation"]["problems"])
                code = 2
            self.cp.meta["active_seconds"] = report["runtime_seconds"]
            self.cp.save()
            return code
        finally:
            self.st.release_lock(lock)
