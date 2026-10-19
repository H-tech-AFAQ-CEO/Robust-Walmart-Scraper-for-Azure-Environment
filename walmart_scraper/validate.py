"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Run-level validation. Any failure => run is NOT published; last good data stays.
"""
from __future__ import annotations
from collections import Counter
from .schema import FIELDS

REQ_COMPLETE = ["product_title", "regular_price", "url", "image_url", "category", "zipcode", "crawl_date"]


def completeness(records: list[dict]) -> dict:
    n = len(records) or 1
    return {f: round(sum(1 for r in records if r.get(f, "") != "") / n, 4) for f in FIELDS}


def validate_run(records: list[dict], cp, prior_report: dict | None, expected_categories: list[str],
                 canaries: list[str], settings, store_verified: bool) -> dict:
    problems: list[str] = []
    warnings: list[str] = []
    by_cat = Counter(r["category"] for r in records)
    prior_cat = (prior_report or {}).get("by_category", {})

    if not store_verified:
        problems.append("store/fulfillment context not verified")
    if cp.counters.get("store_mismatch", 0):
        problems.append(f"store mismatch seen on {cp.counters['store_mismatch']} page(s)")
    for c in expected_categories:
        if by_cat.get(c, 0) == 0:
            problems.append(f"category '{c}' returned zero records")
        elif c in prior_cat and prior_cat[c] and by_cat[c] < settings.min_yield_ratio * prior_cat[c]:
            problems.append(f"category '{c}' yield {by_cat[c]} < {settings.min_yield_ratio:.0%} of prior {prior_cat[c]}")
    failed = [k for k, n in cp.nodes.items() if n.get("status") == "failed"]
    if failed:
        problems.append(f"{len(failed)} listing node(s) failed/blocked (not legitimate empties): {failed[:5]}")
    pending = [k for k, n in cp.nodes.items() if n.get("status") not in ("done", "failed")]
    if pending:
        problems.append(f"{len(pending)} node(s) incomplete")
    # schema/dup
    ids = [r.get("url") for r in records]
    dups = len(ids) - len(set(ids))
    if dups:
        problems.append(f"{dups} duplicate urls in output")
    comp = completeness(records)
    for f in REQ_COMPLETE:
        if records and comp[f] < settings.min_completeness:
            problems.append(f"completeness {f}={comp[f]:.1%} < {settings.min_completeness:.0%}")
    if any(r.get("gupc") or r.get("unit_price") for r in records):
        problems.append("gupc/unit_price must be empty at scraper stage")
    if any("approx" in r.get("weight", "").lower() for r in records):
        problems.append("approximate-weight record present")
    # canaries
    if canaries:
        have = {u for r in records for u in [r.get("url", "")]}
        found = sum(1 for c in canaries if any(f"/{c}" in u for u in have))
        ratio = found / len(canaries)
        if ratio < settings.min_canary_ratio:
            problems.append(f"canary products found {found}/{len(canaries)}")
    else:
        warnings.append("no canary products configured for this location")
    # yield vs prior (overall)
    if prior_report and prior_report.get("total") and len(records) < settings.min_yield_ratio * prior_report["total"]:
        problems.append(f"total {len(records)} < {settings.min_yield_ratio:.0%} of prior {prior_report['total']}")
    if not records:
        problems.append("no records")
    return {"passed": not problems, "problems": problems, "warnings": warnings,
            "completeness": comp, "duplicates_in_output": dups}
