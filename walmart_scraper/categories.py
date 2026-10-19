"""
Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

Subcategory discovery from category pages, with CSV-driven exclusions.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

SKIP_NAMES = re.compile(r"^(shop all|see all|view all|recipes?|all departments|departments|services|walmart\+?)", re.I)


def _cat_id(url: str) -> str:
    m = re.search(r"/(?:cp|browse)/(?:[^/?]+/)*([\d_]+)(?:\?|$|/)", url + "/")
    return m.group(1) if m else ""


def discover_children(parent_url: str, links: list[dict], excluded: list[str]) -> list[dict]:
    """Keep links that look like descendants of parent (id prefix match for /browse/ ids,
    or /cp/ links that are not the parent). Dedupe by cleaned URL."""
    pid = _cat_id(parent_url)
    out, seen = [], set()
    ex = [e.lower() for e in excluded]
    for l in links:
        name, url = l["name"].strip(), l["url"].split("#")[0]
        clean = url.split("?")[0]
        cid = _cat_id(clean)
        if not cid or clean == parent_url.split("?")[0] or clean in seen:
            continue
        if SKIP_NAMES.search(name) or any(e == name.lower() or e in name.lower() for e in ex):
            continue
        is_browse_child = "/browse/" in clean and pid and (cid.startswith(pid.split("_")[-1]) or
                                                             pid.split("_")[-1] in cid.split("_"))
        is_cp_child = "/cp/" in clean and urlparse(clean).netloc.endswith("walmart.com") and "/cp/" in parent_url
        if is_browse_child or is_cp_child:
            seen.add(clean)
            out.append({"name": name, "url": clean})
    return out
