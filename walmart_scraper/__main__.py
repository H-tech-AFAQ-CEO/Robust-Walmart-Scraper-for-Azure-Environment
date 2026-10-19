"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)
"""
import argparse, json, logging, sys
from .config import Settings, load_categories, load_locations
from .storage import make_storage


def main(argv=None):
    ap = argparse.ArgumentParser("walmart_scraper")
    ap.add_argument("command", choices=["run", "probe"])
    ap.add_argument("--location", action="append", help="location id(s); default all enabled")
    ap.add_argument("--fresh", action="store_true", help="ignore any resumable run")
    ap.add_argument("--category", action="append", help="limit to category name(s) (demo/testing)")
    a = ap.parse_args(argv)
    s = Settings.from_env()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format=json.dumps({"ts": "%(asctime)s", "lvl": "%(levelname)s", "log": "%(name)s",
                                           "msg": "%(message)s"}))
    cats = load_categories(f"{s.config_dir}/categories.csv")
    if a.category:
        cats = [c for c in cats if c.name in a.category]
    locs = [l for l in load_locations(f"{s.config_dir}/locations.json") if not a.location or l.id in a.location]
    if not locs:
        print("no matching locations"); return 1
    from .fetcher import BrowserFetcher
    from .runner import Job
    storage = make_storage(s)
    worst = 0
    for loc in locs:
        f = BrowserFetcher(s, loc)
        if a.command == "probe":
            return probe(s, loc, cats[0], f)
        worst = max(worst, Job(loc, cats, s, storage, f).run(fresh=a.fresh))
    return worst


def probe(s, loc, cat, f):
    """Calibration aid: select the store, load one listing, print what the payload says."""
    from . import parser as P
    f.start()
    try:
        f.select_store()
        pg = f.fetch(cat.url, want_links=True)
        print(json.dumps({"blocked": pg.blocked, "reason": pg.reason, "status": pg.status,
                          "store_context": P.extract_store_context(pg.next_data or {}),
                          "items_found": len(P.extract_items(pg.next_data or {})),
                          "max_page": P.max_page(pg.next_data or {}),
                          "sub_links_sample": pg.sub_links[:15]}, indent=2))
        if pg.next_data:
            items = P.extract_items(pg.next_data)
            if items:
                print("FIRST ITEM KEYS:", sorted(items[0].keys()))
        f.screenshot("probe.png")
    finally:
        f.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
